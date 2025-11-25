#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fix incorrect Wikidata matches in the knowledge graph.

This script:
1. Identifies concepts with Wikidata Q-IDs
2. Re-validates them using improved matching logic
3. Updates incorrect matches
"""

import os
import sys
from pathlib import Path

try:
    from rdflib import Graph, Namespace, Literal
    from rdflib.namespace import RDF, RDFS, OWL
except ImportError:
    print("ERROR: rdflib is not installed.")
    sys.exit(1)

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.knowledge_graph.enrich_with_wikidata import (
    find_best_wikidata_match, get_wikidata_labels
)
from scripts.knowledge_graph.load_cc_cedict import (
    load_cedict_file, get_english_translations, find_cedict_file
)

# Configuration
KG_FILE = project_root / 'knowledge_graph' / 'world_model_cwn.ttl'
SRS_KG = Namespace("http://srs4autism.com/schema/")

def main():
    print("=" * 80)
    print("Fix Incorrect Wikidata Matches")
    print("=" * 80)
    print()
    
    # Load CC-CEDICT
    print("Loading CC-CEDICT...")
    cedict_file = find_cedict_file()
    if not cedict_file:
        print("❌ CC-CEDICT not found")
        sys.exit(1)
    cedict_data = load_cedict_file(cedict_file)
    print()
    
    # Load knowledge graph
    print("Loading knowledge graph...")
    graph = Graph()
    graph.bind("srs-kg", SRS_KG)
    graph.parse(str(KG_FILE), format="turtle")
    print(f"  ✅ Loaded {len(graph)} triples")
    print()
    
    # Find words with Wikidata Q-IDs
    print("Finding words with Wikidata Q-IDs to validate...")
    words_to_check = []
    
    for word_uri, _, _ in graph.triples((None, RDF.type, SRS_KG.Word)):
        chinese_text = None
        for _, _, text_literal in graph.triples((word_uri, SRS_KG.text, None)):
            chinese_text = str(text_literal).strip()
            break
        
        if not chinese_text:
            continue
        
        concept_uri = None
        for _, _, concept in graph.triples((word_uri, SRS_KG.means, None)):
            concept_uri = concept
            break
        
        if not concept_uri:
            continue
        
        # Get current Wikidata Q-ID
        current_qid = None
        for _, _, qid in graph.triples((concept_uri, SRS_KG.wikidataId, None)):
            current_qid = str(qid).strip()
            break
        
        if current_qid:
            words_to_check.append({
                'word_uri': word_uri,
                'chinese_text': chinese_text,
                'concept_uri': concept_uri,
                'current_qid': current_qid
            })
    
    print(f"  Found {len(words_to_check)} words with Wikidata Q-IDs")
    print()
    
    if not words_to_check:
        print("✅ No words to check")
        return
    
    # Validate and fix
    print("Validating matches...")
    fixed_count = 0
    checked_count = 0
    
    for word_info in words_to_check:
        chinese_text = word_info['chinese_text']
        concept_uri = word_info['concept_uri']
        current_qid = word_info['current_qid']
        
        checked_count += 1
        if checked_count % 100 == 0:
            print(f"  Checked {checked_count}/{len(words_to_check)}...")
        
        # Get English translation
        translations = get_english_translations(cedict_data, chinese_text)
        if not translations:
            continue
        
        # Find best match with improved logic
        best_qid = find_best_wikidata_match(translations[0], chinese_word=chinese_text)
        
        if best_qid and best_qid != current_qid:
            # Check if the new match is better
            current_labels = get_wikidata_labels(current_qid, languages=['zh'])
            best_labels = get_wikidata_labels(best_qid, languages=['zh'])
            
            # If new match has Chinese label that matches better, update
            if 'zh' in best_labels:
                best_zh = best_labels['zh']
                if chinese_text in best_zh or best_zh == chinese_text:
                    # Remove old Q-ID
                    graph.remove((concept_uri, SRS_KG.wikidataId, Literal(current_qid)))
                    graph.remove((concept_uri, OWL.sameAs, None))
                    
                    # Add new Q-ID
                    from scripts.knowledge_graph.enrich_with_wikidata import enrich_concept_with_wikidata
                    enrich_concept_with_wikidata(graph, concept_uri, best_qid)
                    
                    fixed_count += 1
                    print(f"  ✅ Fixed {chinese_text}: {current_qid} → {best_qid}")
    
    print()
    print(f"✅ Fixed {fixed_count} incorrect matches out of {checked_count} checked")
    print()
    
    # Save
    print("Saving updated graph...")
    graph.serialize(destination=str(KG_FILE), format="turtle")
    print(f"  ✅ Saved to {KG_FILE}")

if __name__ == "__main__":
    main()


