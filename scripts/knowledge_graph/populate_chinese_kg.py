#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Populate Chinese Knowledge Graph from CSV data.

This script reads Chinese vocabulary from CSV files and generates a
knowledge graph in Turtle format conforming to the SRS4Autism ontology schema.
"""

import os
import sys
import csv
import re
from collections import defaultdict
from urllib.parse import quote

try:
    from rdflib import Graph, Namespace, Literal, URIRef
    from rdflib.namespace import RDF, RDFS, SKOS
except ImportError:
    print("ERROR: rdflib is not installed.")
    print("Please install it with: pip install rdflib")
    sys.exit(1)

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, project_root)

# Configuration
DATA_DIR = os.path.join(project_root, 'data', 'content_db')
ONTOLOGY_DIR = os.path.join(project_root, 'knowledge_graph', 'ontology')
OUTPUT_FILE = os.path.join(project_root, 'knowledge_graph', 'world_model.ttl')

# CSV files
BASIC_WORDS_CSV = os.path.join(DATA_DIR, 'basic_words.csv')
ENG_RECOVERED_CSV = os.path.join(DATA_DIR, 'eng_recovered.csv')
ONTOLOGY_FILE = os.path.join(ONTOLOGY_DIR, 'srs_schema.ttl')

# RDF Namespaces
SRS_KG = Namespace("http://srs4autism.com/schema/")
RDF_NS = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")
RDFS_NS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
SKOS_NS = Namespace("http://www.w3.org/2004/02/skos/core#")


def generate_slug(text):
    """Generate a URL-safe slug from Chinese or English text.
    
    For Chinese characters, uses direct UTF-8 (IRIs support Unicode).
    For English, creates a lowercase hyphenated slug.
    """
    if re.search(r'[\u4e00-\u9fff]', text):
        # Chinese characters - use direct UTF-8 (IRIs support Unicode)
        # Keep Chinese characters as-is for readability
        return text
    else:
        # English - convert to lowercase, replace spaces/special chars with hyphens
        slug = re.sub(r'[^\w\s-]', '', text.lower())
        slug = re.sub(r'[-\s]+', '-', slug)
        return slug[:50]  # Limit length


def extract_characters(chinese_text):
    """Extract individual Chinese characters from text."""
    # Match Chinese characters
    chars = re.findall(r'[\u4e00-\u9fff]', chinese_text)
    return chars


def normalize_pinyin(pinyin):
    """Normalize pinyin string (remove spaces, handle tones)."""
    if not pinyin:
        return ""
    # Remove spaces and normalize
    return pinyin.strip()


def create_character_node(graph, char, char_slug, definitions_map):
    """Create a Character node in the graph."""
    char_uri = SRS_KG[f"char-{char_slug}"]
    
    # Avoid duplicates
    if (char_uri, RDF.type, SRS_KG.Character) in graph:
        return char_uri
    
    graph.add((char_uri, RDF.type, SRS_KG.Character))
    graph.add((char_uri, RDFS.label, Literal(char, lang="zh")))
    graph.add((char_uri, SRS_KG.glyph, Literal(char, lang="zh")))
    
    # Add definition if available
    if char in definitions_map:
        graph.add((char_uri, SRS_KG.definition, Literal(definitions_map[char], lang="en")))
    
    return char_uri


def create_word_node(graph, chinese_text, pinyin, english, word_slug, char_nodes):
    """Create a Word node and link it to character nodes."""
    word_uri = SRS_KG[f"word-{word_slug}"]
    
    # Avoid duplicates
    if (word_uri, RDF.type, SRS_KG.Word) in graph:
        return word_uri
    
    graph.add((word_uri, RDF.type, SRS_KG.Word))
    graph.add((word_uri, RDFS.label, Literal(chinese_text, lang="zh")))
    graph.add((word_uri, SRS_KG.text, Literal(chinese_text, lang="zh")))
    
    if pinyin:
        graph.add((word_uri, SRS_KG.pinyin, Literal(normalize_pinyin(pinyin), lang="zh-Latn")))
    
    if english:
        graph.add((word_uri, SRS_KG.definition, Literal(english, lang="en")))
    
    # Link to characters
    for char_node in char_nodes:
        graph.add((word_uri, SRS_KG.composedOf, char_node))
        graph.add((word_uri, SRS_KG.requiresPrerequisite, char_node))
    
    return word_uri


def create_concept_node(graph, english_concept, concept_slug):
    """Create a Concept node based on English translation."""
    concept_uri = SRS_KG[f"concept-{concept_slug}"]
    
    # Avoid duplicates
    if (concept_uri, RDF.type, SRS_KG.Concept) in graph:
        return concept_uri
    
    graph.add((concept_uri, RDF.type, SRS_KG.Concept))
    graph.add((concept_uri, RDFS.label, Literal(f"concept:{english_concept}", lang="en")))
    graph.add((concept_uri, RDFS.comment, Literal(english_concept, lang="en")))
    
    return concept_uri


def load_csv_data(csv_file):
    """Load vocabulary data from CSV file."""
    words = []
    
    if not os.path.exists(csv_file):
        print(f"WARNING: CSV file not found: {csv_file}")
        return words
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Handle different column name variations
                english = row.get('English', row.get('english', '')).strip()
                chinese = row.get('Chinese (Simplified)', row.get('Chinese', row.get('chinese', ''))).strip()
                pinyin = row.get('Pinyin', row.get('pinyin', '')).strip()
                
                if english and chinese:
                    words.append({
                        'english': english,
                        'chinese': chinese,
                        'pinyin': pinyin
                    })
    except Exception as e:
        print(f"ERROR reading {csv_file}: {e}")
    
    return words


def build_character_definitions(words):
    """Build a mapping of characters to their most common English definitions."""
    char_defs = defaultdict(list)
    
    for word in words:
        chars = extract_characters(word['chinese'])
        for char in chars:
            # Use the English word as a definition hint
            char_defs[char].append(word['english'])
    
    # Take the first (most common) definition for each character
    return {char: defs[0] if defs else "" for char, defs in char_defs.items()}


def main():
    """Main function to populate the knowledge graph."""
    print("=" * 80)
    print("Chinese Knowledge Graph Generator")
    print("=" * 80)
    print()
    
    # Initialize RDF graph
    graph = Graph()
    
    # Bind namespaces
    graph.bind("rdf", RDF_NS)
    graph.bind("rdfs", RDFS_NS)
    graph.bind("skos", SKOS_NS)
    graph.bind("srs-kg", SRS_KG)
    
    # Load ontology schema if it exists
    if os.path.exists(ONTOLOGY_FILE):
        print(f"Loading ontology schema from: {ONTOLOGY_FILE}")
        try:
            # Try to parse the ontology (may have syntax issues)
            graph.parse(ONTOLOGY_FILE, format="turtle")
            print("✅ Ontology schema loaded successfully")
        except Exception as e:
            print(f"⚠️  WARNING: Could not parse ontology file: {e}")
            print("   Continuing without pre-loading schema...")
        print()
    else:
        print(f"⚠️  WARNING: Ontology file not found: {ONTOLOGY_FILE}")
        print("   The schema will be defined in the output file.")
        print()
    
    # Load vocabulary data
    print("Loading vocabulary data...")
    all_words = []
    
    # Load from basic_words.csv
    if os.path.exists(BASIC_WORDS_CSV):
        words1 = load_csv_data(BASIC_WORDS_CSV)
        print(f"  ✅ Loaded {len(words1)} words from basic_words.csv")
        all_words.extend(words1)
    else:
        print(f"  ⚠️  File not found: {BASIC_WORDS_CSV}")
    
    # Load from eng_recovered.csv
    if os.path.exists(ENG_RECOVERED_CSV):
        words2 = load_csv_data(ENG_RECOVERED_CSV)
        print(f"  ✅ Loaded {len(words2)} words from eng_recovered.csv")
        all_words.extend(words2)
    else:
        print(f"  ⚠️  File not found: {ENG_RECOVERED_CSV}")
    
    if not all_words:
        print("ERROR: No vocabulary data found. Exiting.")
        sys.exit(1)
    
    print(f"\nTotal words to process: {len(all_words)}")
    print()
    
    # Build character definitions
    print("Building character definitions...")
    char_definitions = build_character_definitions(all_words)
    print(f"  Found {len(char_definitions)} unique characters")
    print()
    
    # Track concepts to avoid duplicates and group synonyms
    concept_map = {}  # english -> concept_uri
    char_nodes = {}   # char -> char_uri
    
    # Process words
    print("Generating knowledge graph triples...")
    word_count = 0
    char_count = 0
    concept_count = 0
    
    for word_data in all_words:
        english = word_data['english']
        chinese = word_data['chinese']
        pinyin = word_data['pinyin']
        
        # Generate slugs
        word_slug = generate_slug(chinese)
        concept_slug = generate_slug(english.lower())
        
        # Extract characters
        chars = extract_characters(chinese)
        
        # Create character nodes
        char_uris = []
        for char in chars:
            if char not in char_nodes:
                char_slug = generate_slug(char)
                char_uri = create_character_node(graph, char, char_slug, char_definitions)
                char_nodes[char] = char_uri
                char_count += 1
            char_uris.append(char_nodes[char])
        
        # Create word node
        word_uri = create_word_node(graph, chinese, pinyin, english, word_slug, char_uris)
        word_count += 1
        
        # Create concept node (one per English translation)
        if concept_slug not in concept_map:
            concept_uri = create_concept_node(graph, english, concept_slug)
            concept_map[concept_slug] = concept_uri
            concept_count += 1
        else:
            concept_uri = concept_map[concept_slug]
        
        # Link word to concept
        graph.add((word_uri, SRS_KG.means, concept_uri))
        
        # Progress indicator
        if word_count % 50 == 0:
            print(f"  Processed {word_count} words...")
    
    print(f"\n✅ Generated knowledge graph:")
    print(f"   - {word_count} words")
    print(f"   - {char_count} characters")
    print(f"   - {concept_count} concepts")
    print()
    
    # Ensure output directory exists
    output_dir = os.path.dirname(OUTPUT_FILE)
    os.makedirs(output_dir, exist_ok=True)
    
    # Serialize to Turtle format
    print(f"Writing knowledge graph to: {OUTPUT_FILE}")
    try:
        graph.serialize(destination=OUTPUT_FILE, format="turtle", encoding="utf-8")
        file_size = os.path.getsize(OUTPUT_FILE)
        print(f"✅ Successfully wrote {file_size:,} bytes to {OUTPUT_FILE}")
    except Exception as e:
        print(f"ERROR writing output file: {e}")
        sys.exit(1)
    
    print()
    print("=" * 80)
    print("Knowledge graph generation complete!")
    print("=" * 80)
    print(f"\nYou can now:")
    print(f"  1. Open {OUTPUT_FILE} in Protégé to visualize the graph")
    print(f"  2. Query the graph using rdflib in your Python scripts")
    print(f"  3. Use the graph for recommendation algorithms")


if __name__ == "__main__":
    main()

