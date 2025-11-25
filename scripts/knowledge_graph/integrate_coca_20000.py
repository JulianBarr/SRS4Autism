#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integrate COCA 20000 word list into English Knowledge Graph.

COCA (Corpus of Contemporary American English) provides a frequency-based
list of the 20,000 most common English words. This script integrates these
words into the existing English KG to fill gaps from CEFR-J vocabulary.

Usage:
    python integrate_coca_20000.py [--coca-file path/to/coca.csv] [--merge]
"""

import os
import sys
import csv
import json
import argparse
import re
from pathlib import Path
from typing import List, Dict, Set, Optional
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
KG_FILE = project_root / 'knowledge_graph' / 'world_model_english.ttl'
ONTOLOGY_FILE = project_root / 'knowledge_graph' / 'ontology' / 'srs_schema.ttl'

# RDF Namespaces
SRS_KG = Namespace("http://srs4autism.com/schema/")


def load_coca_csv(coca_file: Path) -> List[Dict[str, any]]:
    """
    Load COCA word list from CSV file.
    
    Expected formats:
    1. Simple: word,rank,frequency
    2. Detailed: word,rank,frequency,dispersion,range,...
    3. WordFrequency.info format: word,lemma,frequency,...
    
    Returns:
        List of dicts with word, rank, frequency
    """
    words = []
    
    if not coca_file.exists():
        print(f"❌ COCA file not found: {coca_file}")
        return words
    
    try:
        with open(coca_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                # Try different column name variations
                word = (
                    row.get('word', '') or 
                    row.get('Word', '') or 
                    row.get('WORD', '') or
                    row.get('lemma', '') or
                    row.get('Lemma', '')
                ).strip()
                
                rank_str = (
                    row.get('rank', '') or
                    row.get('Rank', '') or
                    row.get('RANK', '') or
                    row.get('#', '')
                ).strip()
                
                freq_str = (
                    row.get('frequency', '') or
                    row.get('Frequency', '') or
                    row.get('FREQUENCY', '') or
                    row.get('freq', '') or
                    row.get('Freq', '')
                ).strip()
                
                pos = (
                    row.get('pos', '') or
                    row.get('POS', '') or
                    row.get('part_of_speech', '')
                ).strip()
                
                if not word:
                    continue
                
                # Parse rank and frequency
                try:
                    rank = int(rank_str) if rank_str and rank_str.isdigit() else None
                    frequency = int(freq_str.replace(',', '')) if freq_str and freq_str.replace(',', '').isdigit() else None
                except:
                    rank = None
                    frequency = None
                
                words.append({
                    'word': word,
                    'rank': rank,
                    'frequency': frequency,
                    'pos': pos
                })
    
    except Exception as e:
        print(f"❌ Error reading COCA file: {e}")
        return words
    
    return words


def load_existing_kg_words(kg_file: Path) -> Set[str]:
    """Load existing word texts from KG to avoid duplicates."""
    existing_words = set()
    
    if not kg_file.exists():
        return existing_words
    
    try:
        graph = Graph()
        graph.parse(str(kg_file), format="turtle")
        
        for word_uri, _, _ in graph.triples((None, RDF.type, SRS_KG.Word)):
            for _, _, label in graph.triples((word_uri, RDFS.label, None)):
                if hasattr(label, 'language') and label.language == 'en':
                    existing_words.add(str(label).lower())
    
    except Exception as e:
        print(f"⚠️  Warning: Could not load existing KG: {e}")
    
    return existing_words


def estimate_cefr_level(rank: Optional[int]) -> Optional[str]:
    """
    Estimate CEFR level based on COCA rank.
    
    This is a rough heuristic - lower rank = higher frequency = lower CEFR level.
    """
    if rank is None:
        return None
    
    # Rough estimates (may need adjustment):
    # Top 1-1000: A1-A2 (most common)
    # 1001-5000: B1-B2 (common)
    # 5001-10000: B2-C1 (moderately common)
    # 10001-20000: C1-C2 (less common but still frequent)
    
    if rank <= 1000:
        return "A2"  # Most frequent = basic
    elif rank <= 5000:
        return "B1"
    elif rank <= 10000:
        return "B2"
    elif rank <= 20000:
        return "C1"
    else:
        return "C2"


def add_words_to_kg(graph: Graph, words: List[Dict], existing_words: Set[str], 
                    skip_existing: bool = False) -> Dict[str, int]:
    """
    Add COCA words to knowledge graph.
    
    Returns:
        Dict with counts: {'added': int, 'skipped': int, 'updated': int}
    """
    stats = {'added': 0, 'skipped': 0, 'updated': 0}
    
    for word_data in words:
        word_text = word_data['word']
        word_lower = word_text.lower()
        word_exists = word_lower in existing_words
        # Normalize word for URI
        word_slug = word_text.lower().replace(' ', '-').replace('/', '-')
        word_slug = re.sub(r'[^a-z0-9\-]', '', word_slug)
        
        # Create word URI
        word_uri = SRS_KG[f'word-en-{word_slug}']
        
        # Check if word already exists in graph
        if (word_uri, RDF.type, SRS_KG.Word) in graph or word_exists:
            stats['updated'] += 1
        else:
            # Create new word node
            graph.add((word_uri, RDF.type, SRS_KG.Word))
            graph.add((word_uri, RDFS.label, Literal(word_text, lang='en')))
            graph.add((word_uri, SRS_KG.text, Literal(word_text, lang='en')))
            stats['added'] += 1
        
        # Add POS if available
        if word_data.get('pos'):
            graph.add((word_uri, SRS_KG.partOfSpeech, Literal(word_data['pos'])))
        
        # Add estimated CEFR level if rank available
        if word_data.get('rank'):
            cefr_level = estimate_cefr_level(word_data['rank'])
            if cefr_level:
                # Check if CEFR level already exists
                existing_cefr = list(graph.objects(word_uri, SRS_KG.cefrLevel))
                if not existing_cefr:
                    graph.add((word_uri, SRS_KG.cefrLevel, Literal(cefr_level)))
        
        # Add frequency metadata
        if word_data.get('frequency') is not None:
            graph.set((word_uri, SRS_KG.frequency, Literal(float(word_data['frequency']), datatype=XSD.float)))
        
        if word_data.get('rank') is not None:
            graph.set((word_uri, SRS_KG.frequencyRank, Literal(int(word_data['rank']), datatype=XSD.integer)))
        
        # Create or link to concept
        concept_slug = word_text.lower().replace(' ', '-').replace('/', '-')
        concept_slug = re.sub(r'[^a-z0-9\-]', '', concept_slug)
        concept_uri = SRS_KG[f'concept-{concept_slug}']
        
        # Create concept if doesn't exist
        if not (concept_uri, RDF.type, SRS_KG.Concept) in graph:
            graph.add((concept_uri, RDF.type, SRS_KG.Concept))
            graph.add((concept_uri, RDFS.label, Literal(word_text, lang='en')))
        
        # Link word to concept
        if not (word_uri, SRS_KG.means, concept_uri) in graph:
            graph.add((word_uri, SRS_KG.means, concept_uri))
    
    return stats


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Integrate COCA 20000 into English KG')
    parser.add_argument('--coca-file', type=Path, 
                       default=DATA_DIR / 'coca_20000.csv',
                       help='Path to COCA CSV file (default: data/content_db/coca_20000.csv)')
    parser.add_argument('--merge', action='store_true',
                       help='Merge with existing KG (default: create new file)')
    parser.add_argument('--output', type=Path,
                       default=KG_FILE,
                       help='Output KG file (default: knowledge_graph/world_model_english.ttl)')
    parser.add_argument('--skip-existing', action='store_true', default=True,
                       help='Skip words already in KG (default: True)')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("Integrate COCA 20000 into English Knowledge Graph")
    print("=" * 80)
    print()
    
    # Load COCA data
    print(f"Loading COCA word list from: {args.coca_file}")
    coca_words = load_coca_csv(args.coca_file)
    
    if not coca_words:
        print("❌ No words loaded from COCA file.")
        print(f"   Expected CSV format: word,rank,frequency,pos")
        print(f"   Or download from: https://www.wordfrequency.info/")
        sys.exit(1)
    
    print(f"✅ Loaded {len(coca_words)} words from COCA")
    print()
    
    # Load existing KG
    print("Loading existing knowledge graph...")
    graph = Graph()
    graph.bind("srs-kg", SRS_KG)
    
    existing_words = set()
    if args.merge and KG_FILE.exists():
        try:
            graph.parse(str(KG_FILE), format="turtle")
            existing_words = load_existing_kg_words(KG_FILE)
            print(f"✅ Loaded existing KG: {len(existing_words)} words already in graph")
        except Exception as e:
            print(f"⚠️  Warning: Could not parse existing KG: {e}")
            print("   Starting with empty graph...")
    
    # Load ontology
    if ONTOLOGY_FILE.exists():
        try:
            graph.parse(str(ONTOLOGY_FILE), format="turtle")
            print("✅ Schema loaded")
        except Exception as e:
            print(f"⚠️  Warning: Could not parse schema: {e}")
    
    print()
    
    # Add COCA words to KG
    print("Adding COCA words to knowledge graph...")
    stats = add_words_to_kg(graph, coca_words, existing_words, 
                           skip_existing=args.skip_existing)
    
    print(f"✅ Added: {stats['added']}")
    print(f"   Updated: {stats['updated']}")
    print(f"   Skipped (already exists): {stats['skipped']}")
    print()
    
    # Save KG
    print(f"Saving knowledge graph to: {args.output}")
    try:
        graph.serialize(destination=str(args.output), format="turtle")
        print(f"✅ Saved {len(graph)} triples to {args.output.name}")
    except Exception as e:
        print(f"❌ Error saving KG: {e}")
        sys.exit(1)
    
    print()
    print("=" * 80)
    print("✅ Complete!")
    print("=" * 80)
    print()
    print("Next steps:")
    print("1. Review the updated KG")
    print("2. Run populate_english_kg_map_bulk.py again to map more cards")
    print("3. Optionally enrich with Wikidata (enrich_english_with_wikidata.py)")


if __name__ == "__main__":
    main()

