#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Link English words to existing Chinese concepts via CC-CEDICT dictionary.

This script:
1. Loads CC-CEDICT dictionary (English -> Chinese reverse lookup)
2. For each English word, finds Chinese translations
3. Finds those Chinese words in the KG
4. Gets their concepts (which have Wikidata Q-IDs)
5. Links English words to those same concepts

This avoids Wikidata API calls entirely and is much faster!
"""

import os
import sys
import re
from pathlib import Path
from typing import Dict, List, Set, Optional
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

# Import CC-CEDICT loader
from scripts.knowledge_graph.load_cc_cedict import (
    find_cedict_file, load_cedict_file, get_english_translations
)

# Configuration
KG_FILE = project_root / 'knowledge_graph' / 'world_model_merged.ttl'
ONTOLOGY_FILE = project_root / 'knowledge_graph' / 'ontology' / 'srs_schema.ttl'
CEDICT_FILE = project_root / 'data' / 'content_db' / 'cedict_1_0_ts_utf-8_mdbg.txt'

# RDF Namespaces
SRS_KG = Namespace("http://srs4autism.com/schema/")


def normalize_word(word: str) -> str:
    """Normalize word for matching."""
    if not word:
        return ""
    return word.lower().strip()


def build_reverse_cedict(cedict_data: Dict) -> Dict[str, List[str]]:
    """
    Build reverse dictionary: English word -> List of Chinese words.
    
    Args:
        cedict_data: CC-CEDICT data (Chinese -> entries)
    
    Returns:
        Dict mapping normalized English word -> List of Chinese words
    """
    print("Building reverse CC-CEDICT dictionary (English -> Chinese)...")
    english_to_chinese = defaultdict(set)
    
    for chinese_word, entries in cedict_data.items():
        for entry in entries:
            for english_def in entry.get('definitions', []):
                # Extract individual English words from definitions
                # Handle phrases like "good morning", "to eat", etc.
                english_words = extract_english_words(english_def)
                for eng_word in english_words:
                    english_to_chinese[normalize_word(eng_word)].add(chinese_word)
    
    # Convert sets to lists
    result = {eng: list(chinese_set) for eng, chinese_set in english_to_chinese.items()}
    print(f"✅ Built reverse dictionary: {len(result)} English words -> Chinese")
    return result


def extract_english_words(definition: str) -> List[str]:
    """
    Extract individual English words from a definition string.
    Handles phrases, removes common prefixes like "to ", etc.
    """
    if not definition:
        return []
    
    # Remove common prefixes
    definition = re.sub(r'^(to|a|an|the)\s+', '', definition.lower())
    
    # Split by common separators
    words = re.split(r'[,;]\s*|\s+and\s+|\s+or\s+', definition.lower())
    
    english_words = []
    for word in words:
        word = word.strip()
        # Remove parenthetical notes
        word = re.sub(r'\([^)]*\)', '', word)
        word = word.strip()
        
        if word and len(word) > 1:
            # Take first word if it's a phrase
            first_word = word.split()[0] if ' ' in word else word
            # Remove punctuation
            first_word = re.sub(r'[^\w\s]', '', first_word)
            if first_word:
                english_words.append(first_word)
    
    return english_words


def build_chinese_word_to_concept_map(graph: Graph) -> Dict[str, URIRef]:
    """
    Build map from Chinese word text -> concept URI.
    
    Returns:
        Dict mapping Chinese word text -> concept_uri
    """
    print("Building Chinese word to concept map...")
    chinese_char_pattern = re.compile(r'[\u4e00-\u9fff]')
    word_to_concept = {}
    
    for word_uri, _, _ in graph.triples((None, RDF.type, SRS_KG.Word)):
        word_uri_ref = URIRef(word_uri) if isinstance(word_uri, str) else word_uri
        
        # Get labels
        labels = list(graph.objects(word_uri_ref, RDFS.label))
        chinese_word = None
        
        for label in labels:
            label_str = str(label)
            if chinese_char_pattern.search(label_str):
                chinese_word = label_str
                break
        
        if chinese_word:
            # Get concept
            concepts = list(graph.objects(word_uri_ref, SRS_KG.means))
            if concepts:
                word_to_concept[chinese_word] = concepts[0]
    
    print(f"✅ Mapped {len(word_to_concept)} Chinese words to concepts")
    return word_to_concept


def link_english_words_via_cedict(graph: Graph, reverse_cedict: Dict[str, List[str]],
                                  chinese_word_to_concept: Dict[str, URIRef],
                                  sample_size: Optional[int] = None) -> Dict[str, int]:
    """
    Link English words to Chinese concepts via CC-CEDICT.
    
    Returns:
        Dict with counts: {'linked': int, 'not_found': int, 'already_linked': int}
    """
    stats = {'linked': 0, 'not_found': 0, 'already_linked': 0, 'no_chinese_match': 0}
    
    chinese_char_pattern = re.compile(r'[\u4e00-\u9fff]')
    
    # Find all English words
    english_words = []
    for word_uri, _, _ in graph.triples((None, RDF.type, SRS_KG.Word)):
        word_uri_ref = URIRef(word_uri) if isinstance(word_uri, str) else word_uri
        labels = list(graph.objects(word_uri_ref, RDFS.label))
        
        is_english = False
        word_text = None
        for label in labels:
            label_str = str(label)
            eng_lang = getattr(label, 'language', None)
            if (eng_lang == 'en' or not eng_lang) and not chinese_char_pattern.search(label_str):
                is_english = True
                word_text = label_str
                break
        
        if is_english:
            # Get current concept
            concepts = list(graph.objects(word_uri_ref, SRS_KG.means))
            current_concept = concepts[0] if concepts else None
            
            # Check if current concept has Wikidata Q-ID
            current_has_qid = False
            if current_concept:
                qids = list(graph.objects(current_concept, SRS_KG.wikidataId))
                current_has_qid = len(qids) > 0
            
            english_words.append({
                'word_uri': word_uri_ref,
                'word_text': word_text,
                'current_concept': current_concept,
                'current_has_qid': current_has_qid
            })
    
    if sample_size:
        english_words = english_words[:sample_size]
        print(f"Processing sample of {sample_size} English words...")
    else:
        print(f"Processing {len(english_words)} English words...")
    
    print()
    
    for i, word_info in enumerate(english_words, 1):
        word_uri = word_info['word_uri']
        word_text = word_info['word_text']
        current_concept = word_info['current_concept']
        current_has_qid = word_info['current_has_qid']
        
        # Progress indicator
        if i % 100 == 0 or i == 1:
            print(f"  Processing word {i}/{len(english_words)}: {word_text}...", end=' ', flush=True)
        
        # Skip if already linked to a concept with Wikidata Q-ID
        if current_has_qid:
            stats['already_linked'] += 1
            if i % 100 == 0 or i == 1:
                print("(already has Wikidata Q-ID)")
            continue
        
        # Look up Chinese translations in CC-CEDICT
        word_normalized = normalize_word(word_text)
        chinese_translations = reverse_cedict.get(word_normalized, [])
        
        if not chinese_translations:
            stats['not_found'] += 1
            if i % 100 == 0 or i == 1:
                print("(no Chinese translation in CC-CEDICT)")
            continue
        
        # Find the first Chinese word that exists in the KG
        target_concept = None
        matched_chinese = None
        
        for chinese_word in chinese_translations:
            if chinese_word in chinese_word_to_concept:
                target_concept = chinese_word_to_concept[chinese_word]
                matched_chinese = chinese_word
                break
        
        if target_concept:
            # Check if target concept has Wikidata Q-ID
            qids = list(graph.objects(target_concept, SRS_KG.wikidataId))
            if qids:
                # Remove old link
                if current_concept:
                    graph.remove((word_uri, SRS_KG.means, current_concept))
                
                # Add new link to existing concept
                graph.add((word_uri, SRS_KG.means, target_concept))
                stats['linked'] += 1
                
                if i % 100 == 0 or i == 1:
                    print(f"✅ Linked via {matched_chinese} (Q-ID: {qids[0]})")
            else:
                stats['no_chinese_match'] += 1
                if i % 100 == 0 or i == 1:
                    print(f"⚠️  Found {matched_chinese} but concept has no Q-ID")
        else:
            stats['no_chinese_match'] += 1
            if i % 100 == 0 or i == 1:
                print(f"(Chinese translations not in KG: {chinese_translations[:2]})")
    
    return stats


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Link English words to existing Chinese concepts via CC-CEDICT'
    )
    parser.add_argument(
        '--sample',
        type=int,
        help='Process only a sample of N words (for testing)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Do not save changes (just report what would be done)'
    )
    parser.add_argument(
        '--cedict-file',
        type=Path,
        default=CEDICT_FILE,
        help='Path to CC-CEDICT file'
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("Link English Words to Chinese Concepts via CC-CEDICT")
    print("=" * 80)
    print()
    
    # Load CC-CEDICT
    print("Step 1: Loading CC-CEDICT dictionary...")
    if not args.cedict_file.exists():
        print(f"❌ CC-CEDICT file not found: {args.cedict_file}")
        print("   Please download from: https://www.mdbg.net/chinese/dictionary?page=cc-cedict")
        sys.exit(1)
    
    cedict_data = load_cedict_file(args.cedict_file)
    if not cedict_data:
        print("❌ Failed to load CC-CEDICT")
        sys.exit(1)
    
    print()
    
    # Build reverse dictionary
    print("Step 2: Building reverse dictionary (English -> Chinese)...")
    reverse_cedict = build_reverse_cedict(cedict_data)
    print()
    
    # Load knowledge graph
    print("Step 3: Loading knowledge graph...")
    graph = Graph()
    graph.bind("srs-kg", SRS_KG)
    
    if KG_FILE.exists():
        print(f"  Loading from: {KG_FILE}")
        try:
            graph.parse(str(KG_FILE), format="turtle")
            print(f"  ✅ Loaded {len(graph)} triples")
        except Exception as e:
            print(f"  ❌ Error loading graph: {e}")
            sys.exit(1)
    else:
        print(f"  ❌ Knowledge graph file not found: {KG_FILE}")
        sys.exit(1)
    
    print()
    
    # Build Chinese word to concept map
    print("Step 4: Building Chinese word to concept map...")
    chinese_word_to_concept = build_chinese_word_to_concept_map(graph)
    print()
    
    # Link English words
    print("Step 5: Linking English words to Chinese concepts...")
    stats = link_english_words_via_cedict(
        graph, reverse_cedict, chinese_word_to_concept, 
        sample_size=args.sample
    )
    
    print()
    print("=" * 80)
    print("Results:")
    print(f"  ✅ Linked to existing Chinese concepts: {stats['linked']}")
    print(f"  ✅ Already linked (had Wikidata Q-ID): {stats['already_linked']}")
    print(f"  ⚠️  No Chinese translation in CC-CEDICT: {stats['not_found']}")
    print(f"  ⚠️  Chinese translation not in KG: {stats['no_chinese_match']}")
    print("=" * 80)
    
    if not args.dry_run and stats['linked'] > 0:
        print()
        print(f"Saving updated knowledge graph to: {KG_FILE}")
        try:
            os.makedirs(KG_FILE.parent, exist_ok=True)
            graph.serialize(destination=str(KG_FILE), format="turtle")
            print(f"✅ Saved {len(graph)} triples")
        except Exception as e:
            print(f"❌ Error saving graph: {e}")
            sys.exit(1)
    elif args.dry_run:
        print()
        print("(Dry run - no changes saved)")


if __name__ == '__main__':
    main()


