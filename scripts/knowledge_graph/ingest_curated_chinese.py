#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enrich Chinese Word Nodes with Level/Theme Inheritance

This script reads curated Chinese translations from the vision cleanup report
and enriches existing Chinese Word nodes in the Knowledge Graph by copying
learningLevel and learningTheme properties from their parent English Word nodes.

Source: logs/vision_cleanup_report.csv
Input Graph: knowledge_graph/world_model_chinese_enriched.ttl (from apply_curation.py)
Output: knowledge_graph/world_model_complete.ttl
"""

import sys
import csv
from pathlib import Path

# Force output (fixes silent death)
sys.stdout.reconfigure(line_buffering=True)

try:
    from rdflib import Graph, Namespace, RDF, RDFS, Literal, URIRef
except ImportError as e:
    print(f"❌ Error: Missing libraries. Run: pip install rdflib")
    print(f"   Missing: {e}")
    sys.exit(1)

# --- CONFIGURATION ---
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent  # scripts -> knowledge_graph -> ROOT

CSV_FILE = PROJECT_ROOT / "logs" / "vision_cleanup_report.csv"
# Input file MUST be world_model_chinese_enriched.ttl (from apply_curation.py step)
INPUT_FILE = PROJECT_ROOT / "knowledge_graph" / "world_model_chinese_enriched.ttl"
OUTPUT_FILE = PROJECT_ROOT / "knowledge_graph" / "world_model_complete.ttl"

# RDF Namespaces
SRS_KG = Namespace("http://srs4autism.com/schema/")


def get_word_properties(graph, word_uri):
    """
    Extract learningLevel and learningTheme properties from a word node.
    Returns dict with 'learningLevel' and 'learningTheme' keys (or None if not present).
    """
    props = {}
    
    # Check for learningLevel
    for level in graph.objects(word_uri, SRS_KG.learningLevel):
        props['learningLevel'] = str(level)
        break
    
    # Check for learningTheme
    for theme in graph.objects(word_uri, SRS_KG.learningTheme):
        props['learningTheme'] = str(theme)
        break
    
    return props if props else None


def find_or_create_chinese_word_node(graph, chinese_text, concept_uri):
    """
    Find existing Chinese Word node or create if missing.
    
    Args:
        graph: RDF graph
        chinese_text: Chinese text (e.g., "关于")
        concept_uri: URI of the concept to link to
    
    Returns:
        word_uri: URI of the Chinese word node (or None if creation failed)
        is_new: True if node was newly created, False if it already existed
    """
    # Validate Chinese text
    chinese_text = chinese_text.strip()
    if not chinese_text:
        return None, False
    
    # Create URI with UTF-8 Chinese text (rdflib handles UTF-8 IRIs correctly)
    word_uri = URIRef(SRS_KG[f"word-zh-{chinese_text}"])
    
    # Check if node already exists
    is_new = (word_uri, RDF.type, SRS_KG.Word) not in graph
    
    if is_new:
        # Create new node if missing
        graph.add((word_uri, RDF.type, SRS_KG.Word))
        graph.add((word_uri, RDFS.label, Literal(chinese_text, lang="zh")))
        graph.add((word_uri, SRS_KG.text, Literal(chinese_text, lang="zh")))
        graph.add((word_uri, SRS_KG.learningLanguage, Literal("zh")))
        
        # Link word to concept
        graph.add((word_uri, SRS_KG.means, concept_uri))
        graph.add((concept_uri, SRS_KG.isExpressedBy, word_uri))
    
    return word_uri, is_new


def enrich_chinese_word_with_properties(graph, chinese_word_uri, english_props):
    """
    Enrich a Chinese Word node by copying learningLevel and learningTheme
    from the English word if they exist.
    
    Args:
        graph: RDF graph
        chinese_word_uri: URI of the Chinese word node to enrich
        english_props: Dict with learningLevel/learningTheme to inherit
    
    Returns:
        enriched_count: Number of properties added (0-2)
    """
    if not english_props:
        return 0
    
    enriched_count = 0
    
    # Check if Chinese word already has these properties
    existing_level = list(graph.objects(chinese_word_uri, SRS_KG.learningLevel))
    existing_theme = list(graph.objects(chinese_word_uri, SRS_KG.learningTheme))
    
    # Add learningLevel if English has it and Chinese doesn't
    if 'learningLevel' in english_props and not existing_level:
        graph.add((chinese_word_uri, SRS_KG.learningLevel, Literal(english_props['learningLevel'])))
        enriched_count += 1
    
    # Add learningTheme if English has it and Chinese doesn't
    if 'learningTheme' in english_props and not existing_theme:
        graph.add((chinese_word_uri, SRS_KG.learningTheme, Literal(english_props['learningTheme'])))
        enriched_count += 1
    
    return enriched_count


def main():
    """Main function to enrich Chinese word nodes with level/theme inheritance."""
    print("=" * 60)
    print("Chinese Vocabulary Enrichment Script")
    print("=" * 60)
    print()
    
    # 1. Load Knowledge Graph
    print(f"[1/5] Loading Knowledge Graph from {INPUT_FILE.name}...")
    if not INPUT_FILE.exists():
        print(f"❌ Error: Input file not found: {INPUT_FILE}")
        print(f"   This file should be created by apply_curation.py first.")
        print(f"   Please run the curation pipeline before this script.")
        return
    
    graph = Graph()
    try:
        graph.parse(INPUT_FILE, format="turtle")
        print(f"   ✅ Loaded {len(graph)} triples.")
    except Exception as e:
        print(f"❌ Error loading graph: {e}")
        return
    
    # 2. Load CSV data
    print(f"\n[2/5] Reading curated translations from {CSV_FILE.name}...")
    if not CSV_FILE.exists():
        print(f"❌ Error: CSV file not found: {CSV_FILE}")
        return
    
    rows = []
    try:
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Skip rows with empty Chinese
                chinese = row.get('Chinese', '').strip()
                if not chinese:
                    continue
                
                # Skip rows marked for deletion
                new_filename = row.get('New_Filename', '').strip()
                if new_filename.upper() == 'DELETE':
                    continue
                
                english_word = row.get('English_Word', '').strip()
                if not english_word:
                    continue
                
                rows.append({
                    'english': english_word,
                    'chinese': chinese
                })
        
        print(f"   ✅ Found {len(rows)} rows with Chinese translations.")
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        return
    
    # 3. Build English word index (for faster lookup)
    print(f"\n[3/5] Building English word index...")
    eng_index = {}  # english_word_lower -> (word_uri, concept_uri)
    q_eng = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    SELECT ?word ?wordLabel ?concept WHERE {
        ?word a srs-kg:Word ;
              srs-kg:text ?wordLabel ;
              srs-kg:means ?concept .
        FILTER (lang(?wordLabel) = "en" || REGEX(STR(?word), "word-en-"))
    }
    """
    for row in graph.query(q_eng):
        label = str(row.wordLabel).lower().strip()
        eng_index[label] = (row.word, row.concept)
    
    print(f"   ✅ Indexed {len(eng_index)} English words.")
    
    # 4. Process rows - enrich existing Chinese nodes
    print(f"\n[4/5] Enriching Chinese word nodes with level/theme inheritance...")
    stats = {
        'processed': 0,
        'enriched': 0,  # Nodes that received new properties
        'created': 0,    # Nodes that were missing and had to be created
        'already_complete': 0,  # Nodes that already had all properties
        'not_found_eng': 0,  # English word not found in KG
        'not_found_concept': 0,  # Concept not found
        'errors': 0
    }
    
    for i, row in enumerate(rows, 1):
        english_word = row['english']
        chinese_text = row['chinese']
        
        try:
            # Look up English word in index
            english_word_lower = english_word.lower().strip()
            if english_word_lower not in eng_index:
                stats['not_found_eng'] += 1
                if i % 100 == 0:
                    print(f"   Processed {i}/{len(rows)}... (English not found: {english_word})", end='\r')
                continue
            
            english_word_uri, concept_uri = eng_index[english_word_lower]
            
            # Get English word properties for inheritance
            english_props = get_word_properties(graph, english_word_uri)
            
            # Find or create Chinese word node
            chinese_word_uri, is_new = find_or_create_chinese_word_node(
                graph, chinese_text, concept_uri
            )
            
            if not chinese_word_uri:
                stats['errors'] += 1
                continue
            
            if is_new:
                stats['created'] += 1
            
            # Enrich with properties from English word
            if english_props:
                enriched_count = enrich_chinese_word_with_properties(
                    graph, chinese_word_uri, english_props
                )
                if enriched_count > 0:
                    stats['enriched'] += 1
                else:
                    stats['already_complete'] += 1
            else:
                # English word has no properties to inherit
                stats['already_complete'] += 1
            
            stats['processed'] += 1
            
            if i % 100 == 0:
                print(f"   Processed {i}/{len(rows)}...", end='\r')
        
        except Exception as e:
            stats['errors'] += 1
            print(f"\n   ⚠️  Error processing '{english_word}' -> '{chinese_text}': {e}")
    
    print(f"\n   ✅ Finished processing {len(rows)} rows.")
    
    # 5. Save output
    print(f"\n[5/5] Saving enriched knowledge graph...")
    try:
        # Ensure output directory exists
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        graph.serialize(destination=OUTPUT_FILE, format="turtle")
        print(f"   ✅ Saved to {OUTPUT_FILE.name}")
    except Exception as e:
        print(f"❌ Error saving graph: {e}")
        return
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Processed rows:           {stats['processed']}")
    print(f"Enriched with properties: {stats['enriched']}")
    print(f"Created new nodes:        {stats['created']}")
    print(f"Already complete:         {stats['already_complete']}")
    print(f"English word not found:   {stats['not_found_eng']}")
    print(f"Errors:                   {stats['errors']}")
    print(f"\nOutput file: {OUTPUT_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()

