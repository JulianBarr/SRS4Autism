#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Propagate Age of Acquisition (AoA) from English words to Chinese words via translations.

Since there's no AoA database for Chinese, we use English AoA as a prior by:
1. Finding Chinese words with English translations (via srs-kg:definition or srs-kg:means -> Concept -> English words)
2. Looking up the AoA of those English translations
3. Adding the AoA to the Chinese words

Usage:
    python propagate_aoa_to_chinese.py [--merge]
"""

import os
import sys
import csv
import argparse
import re
from pathlib import Path
from typing import Dict, Set, Optional, List
from collections import defaultdict

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from rdflib import Graph, Namespace, Literal, URIRef
    from rdflib.namespace import RDF, RDFS, XSD
except ImportError:
    print("ERROR: rdflib is not installed.")
    print("Please install it with: pip install rdflib")
    sys.exit(1)

# Configuration
DATA_DIR = project_root / 'data' / 'content_db'
KG_FILE = project_root / 'knowledge_graph' / 'world_model_merged.ttl'
ONTOLOGY_FILE = project_root / 'knowledge_graph' / 'ontology' / 'srs_schema.ttl'
AOA_FILE = Path('/Users/maxent/src/lingfeat/lingfeat/_LexicoSemantic/resources/AoAKuperman.csv')

# RDF Namespaces
SRS_KG = Namespace("http://srs4autism.com/schema/")


def normalize_word(word: str) -> str:
    """Normalize word for matching (lowercase, strip)."""
    if not word:
        return ""
    return word.lower().strip()


def load_aoa_csv(aoa_file: Path) -> Dict[str, float]:
    """
    Load AoA data from Kuperman CSV file.
    
    Returns:
        Dict mapping normalized word -> AoA value (float)
    """
    aoa_map = {}
    
    if not aoa_file.exists():
        print(f"ERROR: AoA file not found: {aoa_file}")
        return aoa_map
    
    print(f"Loading AoA data from: {aoa_file}")
    
    with open(aoa_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            word = row.get('Word', '').strip()
            # Use AoA_Kup (Kuperman AoA) as primary, fallback to AoA_Kup_lem if available
            aoa_str = row.get('AoA_Kup', '').strip() or row.get('AoA_Kup_lem', '').strip()
            
            if word and aoa_str and aoa_str.lower() != 'none':
                try:
                    aoa_value = float(aoa_str)
                    word_normalized = normalize_word(word)
                    if word_normalized:
                        # Use the first (most common) form if multiple entries exist
                        if word_normalized not in aoa_map:
                            aoa_map[word_normalized] = aoa_value
                        count += 1
                except (ValueError, TypeError):
                    continue
    
    print(f"✅ Loaded {len(aoa_map)} AoA entries")
    return aoa_map


def extract_english_words_from_definition(definition: str) -> List[str]:
    """
    Extract individual English words from a definition string.
    Handles comma-separated definitions like "friend, pal, companion"
    """
    if not definition:
        return []
    
    # Split by comma, semicolon, or "and"
    words = re.split(r'[,;]|\s+and\s+', definition.lower())
    english_words = []
    
    for word in words:
        word = word.strip()
        # Remove common definition markers
        word = re.sub(r'^\(.*?\)\s*', '', word)  # Remove (n.) etc.
        word = re.sub(r'\s*\(.*?\)$', '', word)  # Remove trailing (n.) etc.
        word = word.strip()
        
        # Skip if empty or too short
        if word and len(word) > 1:
            # Take the first word if it's a phrase
            first_word = word.split()[0] if ' ' in word else word
            # Remove punctuation
            first_word = re.sub(r'[^\w\s]', '', first_word)
            if first_word:
                english_words.append(normalize_word(first_word))
    
    return english_words


def find_chinese_words_with_translations(graph: Graph) -> Dict[str, Dict]:
    """
    Find all Chinese words and their English translations.
    
    Returns:
        Dict mapping word_uri -> {
            'label': str (Chinese word),
            'english_words': List[str] (English translations),
            'has_aoa': bool (whether it already has AoA)
        }
    """
    chinese_words = {}
    
    print("Finding Chinese words with English translations...")
    
    # Use direct graph traversal instead of SPARQL for more reliable results
    chinese_char_pattern = re.compile(r'[\u4e00-\u9fff]')
    
    for word_uri, _, _ in graph.triples((None, RDF.type, SRS_KG.Word)):
        word_uri_ref = URIRef(word_uri) if isinstance(word_uri, str) else word_uri
        
        # Get labels
        labels = list(graph.objects(word_uri_ref, RDFS.label))
        chinese_label = None
        
        for label in labels:
            label_str = str(label)
            # Check if it contains Chinese characters
            if chinese_char_pattern.search(label_str):
                chinese_label = label_str
                break
        
        if not chinese_label:
            continue  # Not a Chinese word
        
        # Check if already has AoA
        existing_aoa = list(graph.objects(word_uri_ref, SRS_KG.ageOfAcquisition))
        has_aoa = len(existing_aoa) > 0
        
        english_words = []
        
        # Get English definition directly
        definitions = list(graph.objects(word_uri_ref, SRS_KG.definition))
        for definition in definitions:
            def_lang = getattr(definition, 'language', None)
            if def_lang == 'en' or not def_lang:
                definition_str = str(definition)
                english_words.extend(extract_english_words_from_definition(definition_str))
        
        # Get English words through concept links
        concepts = list(graph.objects(word_uri_ref, SRS_KG.means))
        for concept_uri in concepts:
            # Find English words that mean the same concept
            for eng_word_uri, _, _ in graph.triples((None, SRS_KG.means, concept_uri)):
                eng_labels = list(graph.objects(eng_word_uri, RDFS.label))
                for eng_label in eng_labels:
                    eng_label_str = str(eng_label)
                    eng_lang = getattr(eng_label, 'language', None)
                    # Check if it's an English word (not Chinese)
                    if (eng_lang == 'en' or not eng_lang) and not chinese_char_pattern.search(eng_label_str):
                        english_words.append(normalize_word(eng_label_str))
        
        if english_words:
            chinese_words[str(word_uri)] = {
                'label': chinese_label,
                'english_words': list(set(english_words)),  # Remove duplicates
                'has_aoa': has_aoa
            }
    
    print(f"✅ Found {len(chinese_words)} Chinese words with English translations")
    return chinese_words


def propagate_aoa_to_chinese(graph: Graph, chinese_words: Dict[str, Dict], 
                             aoa_map: Dict[str, float], skip_existing: bool = False) -> Dict[str, int]:
    """
    Propagate AoA from English words to Chinese words.
    
    Returns:
        Dict with counts: {'updated': int, 'not_found': int, 'skipped': int}
    """
    stats = {'updated': 0, 'not_found': 0, 'skipped': 0}
    
    print("\nPropagating AoA to Chinese words...")
    
    for word_uri_str, word_info in chinese_words.items():
        word_uri = URIRef(word_uri_str)
        
        # Skip if already has AoA and skip_existing is True
        if skip_existing and word_info['has_aoa']:
            stats['skipped'] += 1
            continue
        
        # Try to find AoA for any of the English translations
        aoa_value = None
        matched_english_word = None
        
        for english_word in word_info['english_words']:
            if english_word in aoa_map:
                aoa_value = aoa_map[english_word]
                matched_english_word = english_word
                break
        
        if aoa_value is not None:
            # Add or update AoA
            graph.set((word_uri, SRS_KG.ageOfAcquisition, 
                      Literal(float(aoa_value), datatype=XSD.float)))
            stats['updated'] += 1
            
            if stats['updated'] % 100 == 0:
                print(f"  Updated {stats['updated']} Chinese words with AoA...")
        else:
            stats['not_found'] += 1
    
    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Propagate Age of Acquisition (AoA) from English to Chinese words via translations'
    )
    parser.add_argument(
        '--aoa-file',
        type=Path,
        default=AOA_FILE,
        help='Path to AoAKuperman.csv file'
    )
    parser.add_argument(
        '--merge',
        action='store_true',
        help='Merge with existing KG file (world_model_merged.ttl)'
    )
    parser.add_argument(
        '--skip-existing',
        action='store_true',
        help='Skip Chinese words that already have AoA values'
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("AoA Propagation: English -> Chinese (via translations)")
    print("=" * 80)
    print()
    
    # Load AoA data
    aoa_map = load_aoa_csv(args.aoa_file)
    if not aoa_map:
        print("ERROR: No AoA data loaded. Exiting.")
        sys.exit(1)
    
    print()
    
    # Load existing knowledge graph
    graph = Graph()
    graph.bind("srs-kg", SRS_KG)
    
    kg_file_to_use = KG_FILE
    if args.merge:
        kg_file_to_use = project_root / 'knowledge_graph' / 'world_model_merged.ttl'
    
    if kg_file_to_use.exists():
        print(f"Loading existing knowledge graph from: {kg_file_to_use}")
        try:
            graph.parse(str(kg_file_to_use), format="turtle")
            print(f"✅ Loaded existing graph with {len(graph)} triples")
        except Exception as e:
            print(f"⚠️  Warning: Could not parse KG file: {e}")
            print("   Starting with empty graph...")
    else:
        print(f"⚠️  Knowledge graph file not found: {kg_file_to_use}")
        print("   Starting with empty graph...")
    
    print()
    
    # Load ontology schema
    if ONTOLOGY_FILE.exists():
        try:
            graph.parse(str(ONTOLOGY_FILE), format="turtle")
            print("✅ Ontology schema loaded")
        except Exception as e:
            print(f"⚠️  Warning: Could not parse schema: {e}")
    print()
    
    # Find Chinese words with translations
    chinese_words = find_chinese_words_with_translations(graph)
    
    if not chinese_words:
        print("⚠️  No Chinese words with English translations found.")
        print("   Make sure the knowledge graph has been populated with Chinese words and their English definitions.")
        sys.exit(0)
    
    print()
    
    # Propagate AoA
    stats = propagate_aoa_to_chinese(graph, chinese_words, aoa_map, skip_existing=args.skip_existing)
    
    print()
    print(f"✅ Updated {stats['updated']} Chinese words with AoA (from English translations)")
    print(f"   {stats['not_found']} words: English translation not found in AoA database")
    if args.skip_existing:
        print(f"   {stats['skipped']} words: Already had AoA (skipped)")
    print()
    
    # Save updated knowledge graph
    print(f"Saving updated knowledge graph to: {kg_file_to_use}")
    try:
        os.makedirs(kg_file_to_use.parent, exist_ok=True)
        graph.serialize(destination=str(kg_file_to_use), format="turtle")
        print(f"✅ Saved {len(graph)} triples to {kg_file_to_use}")
    except Exception as e:
        print(f"❌ Error saving graph: {e}")
        sys.exit(1)
    
    print()
    print("=" * 80)
    print("AoA Propagation Complete!")
    print("=" * 80)


if __name__ == '__main__':
    main()

