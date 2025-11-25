#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Add English translations to Chinese words in the knowledge graph from basic_words.csv.

This script:
1. Loads English-Chinese mappings from basic_words.csv
2. Finds matching Chinese words in the knowledge graph
3. Adds English definitions (srs-kg:definition with lang="en") to those words
4. This enables the populate_visual_images.py script to match English words from Anki cards
"""

import os
import sys
import csv
import re
from pathlib import Path
from rdflib import Graph, Namespace, RDF, RDFS, Literal
from rdflib.namespace import XSD

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Namespaces
SRS_KG = Namespace("http://srs4autism.com/schema/")

# File paths
KG_FILE = PROJECT_ROOT / "knowledge_graph" / "world_model_cwn.ttl"
CSV_FILE = PROJECT_ROOT / "data" / "content_db" / "basic_words.csv"
SCHEMA_FILE = PROJECT_ROOT / "knowledge_graph" / "ontology" / "srs_schema.ttl"


def load_translations(csv_file):
    """Load English-Chinese translations from CSV file."""
    translations = {}  # chinese -> [english1, english2, ...]
    
    if not csv_file.exists():
        print(f"⚠️  CSV file not found: {csv_file}")
        return translations
    
    print(f"Loading translations from: {csv_file}")
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            chinese = row.get('Chinese (Simplified)', '').strip()
            english = row.get('English', '').strip()
            
            if chinese and english:
                # Handle multiple English translations (comma-separated in CSV)
                english_words = [e.strip() for e in english.split(',')]
                if chinese not in translations:
                    translations[chinese] = []
                translations[chinese].extend(english_words)
    
    print(f"  ✅ Loaded {len(translations)} Chinese words with English translations")
    return translations


def add_english_definitions():
    """Add English definitions to Chinese words in the knowledge graph."""
    print("=" * 80)
    print("Add English Translations to Knowledge Graph")
    print("=" * 80)
    print()
    
    # Load translations
    translations = load_translations(CSV_FILE)
    if not translations:
        print("❌ No translations loaded. Exiting.")
        return
    
    print()
    
    # Load knowledge graph
    print("Loading knowledge graph...")
    graph = Graph()
    graph.bind("srs-kg", SRS_KG)
    
    if not KG_FILE.exists():
        print(f"❌ Knowledge graph file not found: {KG_FILE}")
        return
    
    try:
        graph.parse(str(KG_FILE), format="turtle")
        print(f"  ✅ Loaded {len(graph)} triples")
    except Exception as e:
        print(f"  ❌ Error loading KG: {e}")
        return
    
    print()
    
    # Load schema
    if SCHEMA_FILE.exists():
        try:
            graph.parse(str(SCHEMA_FILE), format="turtle")
            print("  ✅ Schema loaded")
        except Exception as e:
            print(f"  ⚠️  Could not load schema: {e}")
    print()
    
    # Find all Word nodes and add English definitions
    print("Adding English definitions to Chinese words...")
    updated_count = 0
    not_found_count = 0
    already_has_english = 0
    
    word_uris = []
    for word_uri, _, _ in graph.triples((None, RDF.type, SRS_KG.Word)):
        word_uris.append(word_uri)
    
    print(f"  Found {len(word_uris)} Word nodes to check")
    print()
    
    for word_uri in word_uris:
        # Get Chinese word text
        word_text = None
        for _, _, text_literal in graph.triples((word_uri, SRS_KG.text, None)):
            word_text = str(text_literal).strip()
            break
        
        if not word_text:
            continue
        
        # Check if this word has a translation
        if word_text in translations:
            english_words = translations[word_text]
            
            # Check if word already has English definition
            has_english = False
            for _, _, def_obj in graph.triples((word_uri, SRS_KG.definition, None)):
                lang = def_obj.language if hasattr(def_obj, 'language') else None
                if lang == "en" or (lang is None and not any(ord(c) > 127 for c in str(def_obj))):
                    has_english = True
                    break
            
            if has_english:
                already_has_english += 1
                continue
            
            # Add English definitions
            for english_word in english_words:
                # Add as English definition
                graph.add((word_uri, SRS_KG.definition, Literal(english_word, lang="en")))
            
            updated_count += 1
            if updated_count % 50 == 0:
                print(f"  Progress: {updated_count} words updated...")
        else:
            not_found_count += 1
    
    print()
    print(f"  ✅ Updated {updated_count} words with English definitions")
    print(f"  ℹ️  {already_has_english} words already had English definitions")
    print(f"  ℹ️  {not_found_count} words from KG not found in CSV (no translation available)")
    print()
    
    # Save updated knowledge graph
    print("Saving updated knowledge graph...")
    try:
        # Backup original
        backup_file = KG_FILE.with_suffix('.ttl.backup')
        if not backup_file.exists():
            import shutil
            shutil.copy2(KG_FILE, backup_file)
            print(f"  ✅ Created backup: {backup_file}")
        
        # Save updated graph
        graph.serialize(destination=str(KG_FILE), format="turtle")
        print(f"  ✅ Saved to: {KG_FILE}")
        print(f"  ✅ Total triples: {len(graph)}")
    except Exception as e:
        print(f"  ❌ Error saving KG: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print()
    print("=" * 80)
    print("✅ Complete!")
    print("=" * 80)
    print()
    print(f"Next steps:")
    print(f"  1. Re-run populate_visual_images.py --force to link images")
    print(f"  2. The script will now be able to match English words from Anki cards")
    print(f"     to Chinese words via their English definitions")


if __name__ == "__main__":
    add_english_definitions()


