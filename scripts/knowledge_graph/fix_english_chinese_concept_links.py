#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fix incorrect links between English words and Chinese concepts.

The problem: English words are linked to wrong concepts (e.g., "one" linked to Korea concept
instead of "一" concept). This script fixes these by:

1. For each Chinese word with a concept that has a Wikidata Q-ID
2. Find English translations from CC-CEDICT
3. Find those English words in the KG
4. Check if they're linked to the correct concept (same Q-ID)
5. If not, relink them to the correct Chinese concept

This ensures English words share concepts with their Chinese translations.
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
    # Remove common prefixes/suffixes and normalize
    word = word.lower().strip()
    # Remove articles and common words
    word = re.sub(r'^(a|an|the|to|of|in|on|at|for|with|by)\s+', '', word)
    # Remove punctuation
    word = re.sub(r'[^\w\s]', '', word)
    return word.strip()


def extract_first_word(translation: str) -> str:
    """Extract the first meaningful word from a translation string."""
    # Remove parenthetical notes
    translation = re.sub(r'\([^)]*\)', '', translation)
    # Split and get first word
    words = translation.split()
    if words:
        first = words[0].lower().strip('(),;:')
        first = re.sub(r'[^\w]', '', first)
        return first
    return ""


def build_english_word_map(graph: Graph) -> Dict[str, List[URIRef]]:
    """
    Build map from normalized English word -> list of word URIs.
    
    Returns:
        Dict mapping normalized English word -> [word_uri1, word_uri2, ...]
    """
    print("Building English word map...")
    chinese_char_pattern = re.compile(r'[\u4e00-\u9fff]')
    english_word_map = defaultdict(list)
    
    for word_uri, _, _ in graph.triples((None, RDF.type, SRS_KG.Word)):
        word_uri_ref = URIRef(word_uri) if isinstance(word_uri, str) else word_uri
        labels = list(graph.objects(word_uri_ref, RDFS.label))
        
        for label in labels:
            label_str = str(label)
            eng_lang = getattr(label, 'language', None)
            if (eng_lang == 'en' or not eng_lang) and not chinese_char_pattern.search(label_str):
                normalized = normalize_word(label_str)
                if normalized:
                    english_word_map[normalized].append(word_uri_ref)
                # Also add exact match
                exact_normalized = label_str.lower().strip()
                if exact_normalized != normalized:
                    english_word_map[exact_normalized].append(word_uri_ref)
    
    print(f"  Mapped {len(english_word_map)} English word forms to {sum(len(v) for v in english_word_map.values())} word URIs")
    return english_word_map


def fix_english_chinese_links(graph: Graph, cedict_data: Dict, 
                              english_word_map: Dict[str, List[URIRef]],
                              sample_size: Optional[int] = None) -> Dict[str, int]:
    """
    Fix incorrect links between English words and Chinese concepts.
    
    Returns:
        Dict with counts: {'fixed': int, 'already_correct': int, 'not_found': int, 'no_qid': int}
    """
    stats = {'fixed': 0, 'already_correct': 0, 'not_found': 0, 'no_qid': 0, 'no_english_in_kg': 0}
    
    chinese_char_pattern = re.compile(r'[\u4e00-\u9fff]')
    
    # Find all Chinese words with concepts that have Wikidata Q-IDs
    chinese_words_with_qid = []
    
    for word_uri, _, _ in graph.triples((None, RDF.type, SRS_KG.Word)):
        word_uri_ref = URIRef(word_uri) if isinstance(word_uri, str) else word_uri
        labels = list(graph.objects(word_uri_ref, RDFS.label))
        
        chinese_word = None
        for label in labels:
            label_str = str(label)
            if chinese_char_pattern.search(label_str):
                chinese_word = label_str
                break
        
        if chinese_word:
            concepts = list(graph.objects(word_uri_ref, SRS_KG.means))
            if concepts:
                concept_uri = concepts[0]
                qids = list(graph.objects(concept_uri, SRS_KG.wikidataId))
                if qids:
                    chinese_words_with_qid.append({
                        'chinese_word': chinese_word,
                        'concept_uri': concept_uri,
                        'qid': str(qids[0])
                    })
    
    if sample_size:
        chinese_words_with_qid = chinese_words_with_qid[:sample_size]
        print(f"Processing sample of {sample_size} Chinese words with Wikidata Q-IDs...")
    else:
        print(f"Processing {len(chinese_words_with_qid)} Chinese words with Wikidata Q-IDs...")
    
    print()
    
    for i, chinese_info in enumerate(chinese_words_with_qid, 1):
        chinese_word = chinese_info['chinese_word']
        correct_concept = chinese_info['concept_uri']
        correct_qid = chinese_info['qid']
        
        # Progress indicator
        if i % 100 == 0 or i == 1:
            print(f"  Processing {i}/{len(chinese_words_with_qid)}: {chinese_word} (Q-ID: {correct_qid})...", end=' ', flush=True)
        
        # Get English translations from CC-CEDICT
        translations = get_english_translations(cedict_data, chinese_word)
        if not translations:
            stats['not_found'] += 1
            if i % 100 == 0 or i == 1:
                print("(no CC-CEDICT translation)")
            continue
        
        # For each English translation, find the word in KG and fix its link
        # IMPORTANT: Only process the FIRST translation to prioritize the most common meaning
        fixed_any = False
        for translation_idx, translation in enumerate(translations[:3]):  # Check first 3 translations
            # Get exact first word (not extracted from phrase)
            translation_clean = re.sub(r'\([^)]*\)', '', translation)  # Remove parenthetical notes
            words = translation_clean.split()
            if not words:
                continue
            
            exact_first_word = words[0].lower().strip('(),;:')
            exact_first_word = re.sub(r'[^\w]', '', exact_first_word)  # Remove punctuation
            
            # Skip if translation is a multi-word phrase (like "one by one")
            # Only link if the translation is essentially a single word or the word appears standalone
            # This prevents linking "one" from "one by one" to "逐一"
            if len(words) > 1 and 'by' not in [w.lower() for w in words[:3]]:
                # Multi-word phrase, skip unless it's a common pattern like "X by X"
                # Actually, let's be more conservative: only link if translation is single word
                # or starts with semicolon-separated alternatives
                if ';' not in translation and ',' not in translation:
                    # Pure multi-word phrase, skip
                    continue
            
            # Find English word in KG
            english_word_uris = english_word_map.get(exact_first_word, [])
            
            # If exact match not found, skip
            if not english_word_uris:
                continue
            
            # Check each English word URI
            for eng_word_uri in english_word_uris:
                # Get current concept
                current_concepts = list(graph.objects(eng_word_uri, SRS_KG.means))
                current_concept = current_concepts[0] if current_concepts else None
                
                if current_concept == correct_concept:
                    # Already correct
                    stats['already_correct'] += 1
                    continue
                
                # Decision logic for relinking:
                # 1. If current concept has same Q-ID as correct concept, relink (same concept, different URI)
                # 2. If current concept has different Q-ID:
                #    - Only relink if this is the FIRST translation (translation_idx == 0) AND
                #      the correct concept has a Q-ID (prioritize Q-ID linked concepts)
                #    - Otherwise, don't overwrite (existing link might be correct)
                # 3. If current concept has no Q-ID, relink (no strong existing link)
                should_relink = True
                
                if current_concept:
                    current_qids = list(graph.objects(current_concept, SRS_KG.wikidataId))
                    if current_qids:
                        current_qid = str(current_qids[0])
                        if current_qid == correct_qid:
                            # Same Q-ID but different concept URI - should merge, but for now just relink
                            should_relink = True
                        else:
                            # Different Q-IDs - always relink if this is the first translation
                            # (CC-CEDICT first translation is the most common/authoritative meaning)
                            if translation_idx == 0:
                                # First translation = most common meaning, so relink (overwrite existing)
                                should_relink = True
                            else:
                                # Later translation = less common meaning, don't overwrite existing link
                                should_relink = False
                
                if not should_relink:
                    continue
                
                # Relink to correct concept
                if current_concept:
                    graph.remove((eng_word_uri, SRS_KG.means, current_concept))
                
                graph.add((eng_word_uri, SRS_KG.means, correct_concept))
                stats['fixed'] += 1
                fixed_any = True
                
                # Get English word label for logging
                eng_labels = list(graph.objects(eng_word_uri, RDFS.label))
                eng_label = str(eng_labels[0]) if eng_labels else '?'
                
                if i % 100 == 0 or i == 1:
                    print(f"✅ Fixed: {eng_label} -> {chinese_word} concept")
        
        if not fixed_any and i % 100 == 0 or i == 1:
            print("(no fixes needed)")
    
    return stats


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Fix incorrect links between English words and Chinese concepts'
    )
    parser.add_argument(
        '--sample',
        type=int,
        help='Process only a sample of N Chinese words (for testing)'
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
    print("Fix English-Chinese Concept Links")
    print("=" * 80)
    print()
    
    # Load CC-CEDICT
    print("Step 1: Loading CC-CEDICT dictionary...")
    if not args.cedict_file.exists():
        print(f"❌ CC-CEDICT file not found: {args.cedict_file}")
        sys.exit(1)
    
    cedict_data = load_cedict_file(args.cedict_file)
    if not cedict_data:
        print("❌ Failed to load CC-CEDICT")
        sys.exit(1)
    
    print()
    
    # Load knowledge graph
    print("Step 2: Loading knowledge graph...")
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
    
    # Build English word map
    print("Step 3: Building English word map...")
    english_word_map = build_english_word_map(graph)
    print()
    
    # Fix links
    print("Step 4: Fixing incorrect links...")
    stats = fix_english_chinese_links(
        graph, cedict_data, english_word_map, 
        sample_size=args.sample
    )
    
    print()
    print("=" * 80)
    print("Results:")
    print(f"  ✅ Fixed incorrect links: {stats['fixed']}")
    print(f"  ✅ Already correct: {stats['already_correct']}")
    print(f"  ⚠️  No CC-CEDICT translation: {stats['not_found']}")
    print(f"  ⚠️  English word not in KG: {stats['no_english_in_kg']}")
    print(f"  ⚠️  Concept has no Q-ID: {stats['no_qid']}")
    print("=" * 80)
    
    if not args.dry_run and stats['fixed'] > 0:
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

