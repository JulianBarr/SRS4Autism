#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Link English words to existing concepts that have Wikidata Q-IDs.

The problem: English words were created with new concepts, but Chinese words
already have concepts with Wikidata Q-IDs. We need to link English words to
the same concepts that Chinese words use (via Wikidata Q-ID matching).

Strategy:
1. For each English word, search Wikidata to find its Q-ID
2. Find existing concepts with that Q-ID (from Chinese words)
3. Link the English word to that existing concept (instead of its current concept)
"""

import os
import sys
import re
import time
from pathlib import Path
from typing import Dict, Optional, Set
from collections import defaultdict

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from rdflib import Graph, Namespace, Literal, URIRef
    from rdflib.namespace import RDF, RDFS, XSD, OWL
except ImportError:
    print("ERROR: rdflib is not installed.")
    print("Please install it with: pip install rdflib")
    sys.exit(1)

# Import Wikidata functions
sys.path.insert(0, str(project_root / 'scripts' / 'knowledge_graph'))
try:
    from enrich_english_with_wikidata import (
        search_wikidata, get_wikidata_labels, find_best_wikidata_match
    )
except ImportError:
    print("ERROR: Could not import Wikidata functions from enrich_english_with_wikidata.py")
    sys.exit(1)

# Configuration
KG_FILE = project_root / 'knowledge_graph' / 'world_model_merged.ttl'
ONTOLOGY_FILE = project_root / 'knowledge_graph' / 'ontology' / 'srs_schema.ttl'

# RDF Namespaces
SRS_KG = Namespace("http://srs4autism.com/schema/")
WIKIDATA = Namespace("http://www.wikidata.org/entity/")


def build_wikidata_to_concept_map(graph: Graph) -> Dict[str, URIRef]:
    """
    Build a map from Wikidata Q-ID to concept URI.
    
    Returns:
        Dict mapping Q-ID (e.g., "Q34079") -> concept_uri
    """
    qid_to_concept = {}
    
    print("Building Wikidata Q-ID to concept map...")
    for concept_uri, _, qid_literal in graph.triples((None, SRS_KG.wikidataId, None)):
        qid = str(qid_literal)
        if qid not in qid_to_concept:
            qid_to_concept[qid] = concept_uri
    
    print(f"  Found {len(qid_to_concept)} concepts with Wikidata Q-IDs")
    return qid_to_concept


def link_english_words_to_wikidata_concepts(graph: Graph, qid_to_concept: Dict[str, URIRef],
                                            sample_size: Optional[int] = None) -> Dict[str, int]:
    """
    Link English words to existing concepts via Wikidata Q-IDs.
    
    Returns:
        Dict with counts: {'linked': int, 'not_found': int, 'already_linked': int, 'no_qid': int}
    """
    stats = {'linked': 0, 'not_found': 0, 'already_linked': 0, 'no_qid': 0}
    
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
            
            # Get definition
            definitions = list(graph.objects(word_uri_ref, SRS_KG.definition))
            definition = str(definitions[0]) if definitions else None
            
            english_words.append({
                'word_uri': word_uri_ref,
                'word_text': word_text,
                'definition': definition,
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
        definition = word_info['definition']
        current_concept = word_info['current_concept']
        current_has_qid = word_info['current_has_qid']
        
        # Progress indicator
        if i % 10 == 0 or i == 1:
            print(f"  Processing word {i}/{len(english_words)}: {word_text}...", end=' ', flush=True)
        
        # Skip if already linked to a concept with Wikidata Q-ID
        if current_has_qid:
            stats['already_linked'] += 1
            if i % 10 == 0 or i == 1:
                print("(already has Wikidata Q-ID)")
            continue
        
        # Search Wikidata for this English word
        search_terms = []
        if definition:
            search_terms.append(definition)
        search_terms.append(word_text)
        
        try:
            start_time = time.time()
            # Use a shorter timeout for faster failure
            # Note: This modifies the global timeout, but it's acceptable for this script
            import urllib.request
            original_timeout = getattr(urllib.request, '_default_timeout', None)
            urllib.request._default_timeout = 3  # 3 second timeout instead of 10
            
            qid = find_best_wikidata_match(search_terms, word_text=word_text)
            
            # Restore original timeout
            if original_timeout is not None:
                urllib.request._default_timeout = original_timeout
            
            elapsed = time.time() - start_time
            
            if qid and qid in qid_to_concept:
                # Found existing concept with this Q-ID
                existing_concept = qid_to_concept[qid]
                
                # Remove old link
                if current_concept:
                    graph.remove((word_uri, SRS_KG.means, current_concept))
                
                # Add new link to existing concept
                graph.add((word_uri, SRS_KG.means, existing_concept))
                stats['linked'] += 1
                
                if i % 10 == 0 or i == 1:
                    print(f"✅ Linked (Q-ID: {qid}, {elapsed:.1f}s)")
            elif qid:
                stats['no_qid'] += 1
                if i % 10 == 0 or i == 1:
                    print(f"⚠️  Found Q-ID {qid} but no matching concept ({elapsed:.1f}s)")
            else:
                stats['no_qid'] += 1
                if i % 10 == 0 or i == 1:
                    print(f"❌ No Wikidata match ({elapsed:.1f}s)")
        except Exception as e:
            stats['not_found'] += 1
            error_msg = str(e)[:50]  # Truncate long error messages
            if i % 10 == 0 or i == 1:
                print(f"❌ Error: {error_msg}")
            # Log first few errors in detail
            if stats['not_found'] <= 3:
                import traceback
                print(f"    Full error: {traceback.format_exc()}")
        
        # Rate limiting (small delay to be nice to API)
        if i % 10 == 0:
            time.sleep(0.1)
    
    return stats


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Link English words to existing concepts with Wikidata Q-IDs'
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
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("Link English Words to Wikidata Concepts")
    print("=" * 80)
    print()
    
    # Load knowledge graph
    graph = Graph()
    graph.bind("srs-kg", SRS_KG)
    graph.bind("wd", WIKIDATA)
    
    if KG_FILE.exists():
        print(f"Loading knowledge graph from: {KG_FILE}")
        try:
            graph.parse(str(KG_FILE), format="turtle")
            print(f"✅ Loaded graph with {len(graph)} triples")
        except Exception as e:
            print(f"❌ Error loading graph: {e}")
            sys.exit(1)
    else:
        print(f"❌ Knowledge graph file not found: {KG_FILE}")
        sys.exit(1)
    
    print()
    
    # Build Wikidata Q-ID to concept map
    qid_to_concept = build_wikidata_to_concept_map(graph)
    
    if not qid_to_concept:
        print("⚠️  No concepts with Wikidata Q-IDs found.")
        print("   Run enrich_with_wikidata.py first to add Wikidata Q-IDs to Chinese concepts.")
        sys.exit(0)
    
    print()
    
    # Link English words
    stats = link_english_words_to_wikidata_concepts(graph, qid_to_concept, sample_size=args.sample)
    
    print()
    print("=" * 80)
    print("Results:")
    print(f"  Linked to existing Wikidata concepts: {stats['linked']}")
    print(f"  Already linked (had Wikidata Q-ID): {stats['already_linked']}")
    print(f"  No Wikidata Q-ID found: {stats['no_qid']}")
    print(f"  Errors/not found: {stats['not_found']}")
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

