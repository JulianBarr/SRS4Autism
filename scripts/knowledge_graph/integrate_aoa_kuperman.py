#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integrate Age of Acquisition (AoA) data from Kuperman et al. (2012) into English Knowledge Graph.

This script reads the AoAKuperman.csv file and adds AoA ratings to English words in the KG.

Usage:
    python integrate_aoa_kuperman.py [--aoa-file path/to/AoAKuperman.csv] [--merge]
"""

import os
import sys
import csv
import argparse
import re
from pathlib import Path
from typing import Dict, Set, Optional

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


def get_existing_words(graph: Graph) -> Set[str]:
    """Get set of existing word URIs in the graph."""
    existing = set()
    for word_uri, _, _ in graph.triples((None, RDF.type, SRS_KG.Word)):
        existing.add(str(word_uri))
    return existing


def update_words_with_aoa(graph: Graph, aoa_map: Dict[str, float], 
                          skip_existing: bool = False) -> Dict[str, int]:
    """
    Update existing words in graph with AoA data.
    
    Returns:
        Dict with counts: {'updated': int, 'not_found': int}
    """
    stats = {'updated': 0, 'not_found': 0}
    
    # Query all English words
    query = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?word ?label WHERE {
        ?word a srs-kg:Word ;
              rdfs:label ?label .
        FILTER(LANG(?label) = "en" || LANG(?label) = "")
    }
    """
    
    results = graph.query(query)
    
    for row in results:
        word_uri = row.word
        word_label = str(row.label)
        word_normalized = normalize_word(word_label)
        
        if word_normalized in aoa_map:
            aoa_value = aoa_map[word_normalized]
            
            # Check if AoA already exists
            existing_aoa = list(graph.objects(word_uri, SRS_KG.ageOfAcquisition))
            if existing_aoa and skip_existing:
                continue
            
            # Add or update AoA
            graph.set((word_uri, SRS_KG.ageOfAcquisition, 
                      Literal(float(aoa_value), datatype=XSD.float)))
            stats['updated'] += 1
            
            if stats['updated'] % 100 == 0:
                print(f"  Updated {stats['updated']} words with AoA...")
        else:
            stats['not_found'] += 1
    
    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Integrate Age of Acquisition (AoA) data into English Knowledge Graph'
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
        help='Skip words that already have AoA values'
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("Age of Acquisition (AoA) Integration")
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
    
    # Update words with AoA
    print("Updating words with AoA data...")
    stats = update_words_with_aoa(graph, aoa_map, skip_existing=args.skip_existing)
    
    print()
    print(f"✅ Updated {stats['updated']} words with AoA")
    print(f"   {stats['not_found']} words not found in AoA database")
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
    print("AoA Integration Complete!")
    print("=" * 80)


if __name__ == '__main__':
    main()


