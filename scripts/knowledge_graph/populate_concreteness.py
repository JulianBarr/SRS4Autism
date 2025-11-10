#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Populate Knowledge Graph with Word Concreteness Ratings from Brysbaert et al. BRM database.

Since the concreteness database is English-only, this script maps Chinese words
to their English translations (from the definition field) and then looks up
concreteness ratings.
"""

import os
import sys
import csv
import json
import re
from collections import defaultdict

try:
    from rdflib import Graph, Namespace, Literal
    from rdflib.namespace import RDF, RDFS, XSD
except ImportError:
    print("ERROR: rdflib is not installed.")
    print("Please install it with: pip install rdflib")
    sys.exit(1)

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, project_root)

DATA_DIR = os.path.join(project_root, 'data', 'content_db')
ONTOLOGY_DIR = os.path.join(project_root, 'knowledge_graph', 'ontology')
KG_FILE = os.path.join(project_root, 'knowledge_graph', 'world_model_cwn.ttl')
SCHEMA_FILE = os.path.join(ONTOLOGY_DIR, 'srs_schema.ttl')
CONCRETENESS_FILE = os.path.join(DATA_DIR, 'Concreteness_ratings_Brysbaert_et_al_BRM.txt')

SRS_KG = Namespace("http://srs4autism.com/schema/")
INST = Namespace("http://srs4autism.com/instance/")


def normalize_word(word):
    """Normalize English word for matching (lowercase, remove punctuation, handle variations)."""
    if not word:
        return None
    
    # Convert to lowercase
    word = word.lower().strip()
    
    # Remove common punctuation and extra spaces
    word = re.sub(r'[^\w\s]', '', word)
    word = re.sub(r'\s+', ' ', word).strip()
    
    # Handle common variations
    # Remove trailing 's' for plural matching (but keep it if word is very short)
    if len(word) > 3 and word.endswith('s') and not word.endswith('ss'):
        # Could be plural, but don't remove it - we'll match both
        pass
    
    return word if word else None


def load_concreteness_database(file_path):
    """Load concreteness ratings from the BRM database file."""
    concreteness_map = {}
    
    if not os.path.exists(file_path):
        print(f"ERROR: Concreteness file not found: {file_path}")
        return concreteness_map
    
    print(f"Loading concreteness database from: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
            
            for row in reader:
                word = row.get('Word', '').strip()
                conc_m = row.get('Conc.M', '').strip()
                
                if not word or not conc_m:
                    continue
                
                try:
                    concreteness_value = float(conc_m)
                    # Normalize the word for matching
                    normalized = normalize_word(word)
                    if normalized:
                        # Store both original and normalized for flexible matching
                        concreteness_map[normalized] = concreteness_value
                        # Also store original if different
                        if word.lower() != normalized:
                            concreteness_map[word.lower()] = concreteness_value
                except ValueError:
                    continue
        
        print(f"✅ Loaded {len(concreteness_map)} concreteness ratings")
        return concreteness_map
    
    except Exception as e:
        print(f"ERROR loading concreteness database: {e}")
        return concreteness_map


def extract_english_words_from_definition(definition):
    """Extract English words from a definition string.
    
    Handles multiple words, comma-separated lists, and phrases.
    Returns a list of normalized words.
    """
    if not definition:
        return []
    
    # Split by common separators (comma, semicolon, "or", "and", etc.)
    # First, try to split by common patterns
    parts = re.split(r'[,;]\s*|(?:\s+or\s+)|(?:\s+and\s+)', definition, flags=re.IGNORECASE)
    
    words = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        # Remove parenthetical notes
        part = re.sub(r'\([^)]*\)', '', part)
        part = part.strip()
        
        # Try to extract individual words
        # Handle common patterns like "noun: word" or "word (noun)"
        part = re.sub(r'^[^:]+:\s*', '', part)  # Remove prefix like "noun:"
        part = re.sub(r'\s*\([^)]*\)$', '', part)  # Remove suffix like "(noun)"
        
        # Split into individual words and normalize
        word_parts = re.findall(r'\b\w+\b', part.lower())
        for wp in word_parts:
            normalized = normalize_word(wp)
            if normalized and len(normalized) > 2:  # Skip very short words
                words.append(normalized)
    
    # Also try the whole definition as a single phrase
    full_normalized = normalize_word(definition)
    if full_normalized and len(full_normalized) > 2:
        words.append(full_normalized)
    
    return list(set(words))  # Remove duplicates


def find_concreteness_rating(english_words, concreteness_map):
    """Find concreteness rating for a list of English words.
    
    Returns the first matching rating found, or None if no match.
    """
    for word in english_words:
        normalized = normalize_word(word)
        if normalized and normalized in concreteness_map:
            return concreteness_map[normalized]
    
    return None


def load_english_translations_from_hsk_json():
    """Load English translations from complete-hsk-vocabulary JSON files."""
    translation_map = {}  # chinese_word -> [english_words]
    
    HSK_PROJECT_DIR = os.path.join(project_root, '..', 'complete-hsk-vocabulary')
    complete_json = os.path.join(HSK_PROJECT_DIR, 'complete.json')
    
    if not os.path.exists(complete_json):
        print(f"⚠️  complete-hsk-vocabulary not found at: {complete_json}")
        print(f"   Trying alternative location...")
        # Try absolute path
        HSK_PROJECT_DIR = "/Users/maxent/src/complete-hsk-vocabulary"
        complete_json = os.path.join(HSK_PROJECT_DIR, 'complete.json')
    
    if os.path.exists(complete_json):
        print(f"Loading English translations from: complete-hsk-vocabulary/complete.json")
        try:
            with open(complete_json, 'r', encoding='utf-8') as f:
                hsk_data = json.load(f)
            
            for entry in hsk_data:
                simplified = entry.get('simplified', '').strip()
                if not simplified:
                    continue
                
                # Extract meanings from all forms
                all_meanings = []
                for form in entry.get('forms', []):
                    meanings = form.get('meanings', [])
                    all_meanings.extend(meanings)
                
                if all_meanings:
                    # Clean and normalize meanings
                    english_words = []
                    for meaning in all_meanings:
                        # Remove common prefixes/suffixes like "to ", "(language)", etc.
                        meaning = meaning.strip()
                        # Extract key words from phrases
                        # For example: "to love; to be fond of" -> ["love", "fond"]
                        words = extract_english_words_from_definition(meaning)
                        english_words.extend(words)
                    
                    # Also try the raw meanings (they might match directly)
                    for meaning in all_meanings:
                        normalized = normalize_word(meaning)
                        if normalized and len(normalized) > 2:
                            english_words.append(normalized)
                    
                    if english_words:
                        if simplified not in translation_map:
                            translation_map[simplified] = []
                        translation_map[simplified].extend(english_words)
            
            # Deduplicate
            for chinese in translation_map:
                translation_map[chinese] = list(set(translation_map[chinese]))
            
            print(f"✅ Loaded {len(translation_map)} words from complete-hsk-vocabulary")
        except Exception as e:
            print(f"⚠️  Error loading complete.json: {e}")
            import traceback
            traceback.print_exc()
    
    # Also try basic_words.csv and eng_recovered.csv as fallback
    basic_words_file = os.path.join(DATA_DIR, 'basic_words.csv')
    if os.path.exists(basic_words_file):
        print(f"Loading additional translations from: basic_words.csv")
        try:
            with open(basic_words_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    chinese = row.get('Chinese (Simplified)', '').strip() or row.get('chinese', '').strip()
                    english = row.get('English', '').strip() or row.get('english', '').strip()
                    
                    if not chinese or not english:
                        continue
                    
                    english_list = [e.strip() for e in re.split(r'[,;]', english) if e.strip()]
                    
                    if chinese not in translation_map:
                        translation_map[chinese] = []
                    
                    translation_map[chinese].extend(english_list)
            
            # Deduplicate
            for chinese in translation_map:
                translation_map[chinese] = list(set(translation_map[chinese]))
            
            print(f"✅ Added translations from basic_words.csv")
        except Exception as e:
            print(f"⚠️  Error loading basic_words.csv: {e}")
    
    print(f"✅ Total: {len(translation_map)} Chinese words with English translations")
    return translation_map


def load_english_translations():
    """Load English translations from available sources (prefer HSK JSON files)."""
    return load_english_translations_from_hsk_json()


def populate_concreteness():
    """Main function to add concreteness ratings to the knowledge graph."""
    print("=" * 80)
    print("Word Concreteness Rating Populator")
    print("=" * 80)
    print()
    
    # Load concreteness database
    concreteness_map = load_concreteness_database(CONCRETENESS_FILE)
    if not concreteness_map:
        print("ERROR: Could not load concreteness database. Exiting.")
        sys.exit(1)
    
    print()
    
    # Load English translations from available CSV files
    translation_map = load_english_translations()
    print()
    
    # Load existing knowledge graph
    graph = Graph()
    graph.bind("srs-kg", SRS_KG)
    graph.bind("srs-inst", INST)
    
    if os.path.exists(KG_FILE):
        print(f"Loading existing knowledge graph from: {KG_FILE}")
        try:
            graph.parse(KG_FILE, format="turtle")
            print(f"✅ Loaded existing graph with {len(graph)} triples")
        except Exception as e:
            print(f"⚠️  Warning: Could not parse KG file: {e}")
            print("   Starting with empty graph...")
    else:
        print(f"⚠️  Knowledge graph file not found: {KG_FILE}")
        print("   Starting with empty graph...")
    
    print()
    
    # Load ontology schema
    if os.path.exists(SCHEMA_FILE):
        try:
            graph.parse(SCHEMA_FILE, format="turtle")
            print("✅ Ontology schema loaded")
        except Exception as e:
            print(f"⚠️  Warning: Could not parse schema: {e}")
    print()
    
    # Query all words with English definitions
    print("Querying words with English definitions from knowledge graph...")
    
    # SPARQL query to find all words with definitions
    sparql_query = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?word_uri ?word_text ?definition WHERE {
        ?word_uri a srs-kg:Word .
        ?word_uri srs-kg:text ?word_text .
        OPTIONAL { ?word_uri srs-kg:definition ?definition . FILTER(LANG(?definition) = "en" || LANG(?definition) = "") }
    }
    """
    
    # Since we're using RDFLib, we need to query the graph directly
    # We'll iterate through the graph to find words with definitions
    words_with_definitions = []
    words_seen = set()  # Track words we've already processed
    
    # First, find all Word nodes
    for word_uri, _, _ in graph.triples((None, RDF.type, SRS_KG.Word)):
        if word_uri in words_seen:
            continue
        
        # Get the word text
        word_text = None
        for _, _, text_obj in graph.triples((word_uri, SRS_KG.text, None)):
            word_text = str(text_obj)
            break
        
        if not word_text:
            continue
        
        # Try to find English translation
        english_words = []
        
        # Method 1: Look up in translation map (most reliable)
        if word_text in translation_map:
            english_words = translation_map[word_text]
        
        # Method 2: Direct definition property
        if not english_words:
            for _, _, definition_obj in graph.triples((word_uri, SRS_KG.definition, None)):
                definition_str = str(definition_obj)
                lang = definition_obj.language if hasattr(definition_obj, 'language') else None
                
                # Prefer English definitions
                if lang == "en" or (lang is None and not any(ord(c) > 127 for c in definition_str)):
                    english_words = extract_english_words_from_definition(definition_str)
                    if english_words:
                        break
        
        # Method 3: Via Concept node (word -> means -> concept -> label)
        if not english_words:
            for _, _, concept_uri in graph.triples((word_uri, SRS_KG.means, None)):
                # Get concept label
                for _, _, label_obj in graph.triples((concept_uri, RDFS.label, None)):
                    label_str = str(label_obj)
                    lang = label_obj.language if hasattr(label_obj, 'language') else None
                    
                    # Prefer English labels
                    if lang == "en" or (lang is None and not any(ord(c) > 127 for c in label_str)):
                        english_words = extract_english_words_from_definition(label_str)
                        if english_words:
                            break
        
        if english_words:
            words_with_definitions.append({
                'uri': word_uri,
                'text': word_text,
                'english_words': english_words
            })
            words_seen.add(word_uri)
    
    print(f"✅ Found {len(words_with_definitions)} words with English translations")
    print()
    
    # Process words and add concreteness ratings
    print("Processing words and matching with concreteness database...")
    
    matched_count = 0
    unmatched_count = 0
    
    for word_data in words_with_definitions:
        word_uri = word_data['uri']
        word_text = word_data['text']
        english_words = word_data['english_words']
        
        if not english_words:
            unmatched_count += 1
            continue
        
        # Find concreteness rating
        concreteness = find_concreteness_rating(english_words, concreteness_map)
        
        if concreteness is not None:
            # Add concreteness property to word node
            graph.add((word_uri, SRS_KG.concreteness, Literal(concreteness, datatype=XSD.decimal)))
            matched_count += 1
            
            if matched_count % 100 == 0:
                print(f"  Processed {matched_count} words with concreteness ratings...")
        else:
            unmatched_count += 1
    
    print()
    print(f"✅ Matched {matched_count} words with concreteness ratings")
    print(f"   {unmatched_count} words could not be matched")
    print()
    
    # Save updated knowledge graph
    print(f"Saving updated knowledge graph to: {KG_FILE}")
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(KG_FILE), exist_ok=True)
        
        graph.serialize(destination=KG_FILE, format="turtle")
        print(f"✅ Saved knowledge graph with {len(graph)} triples")
        print()
        print("=" * 80)
        print("✅ Concreteness ratings successfully added to knowledge graph!")
        print("=" * 80)
        print()
        print(f"Next steps:")
        print(f"1. Restart Jena Fuseki to load the updated knowledge graph")
        print(f"2. Verify concreteness ratings with a SPARQL query")
        print()
    except Exception as e:
        print(f"ERROR saving knowledge graph: {e}")
        sys.exit(1)


if __name__ == "__main__":
    populate_concreteness()
