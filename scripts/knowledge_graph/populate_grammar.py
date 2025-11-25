#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Populate Knowledge Graph with Grammar Points from Chinese Grammar Wiki.

This script loads grammar data from chinese_grammar_knowledge_graph.json
and integrates it into the existing world_model.ttl, creating GrammarPoint
and Sentence nodes with proper relationships to existing Word nodes.
"""

import os
import sys
import json
import re
from urllib.parse import quote

try:
    from rdflib import Graph, Namespace, Literal
    from rdflib.namespace import RDF, RDFS, XSD
except ImportError:
    print("ERROR: rdflib is not installed.")
    print("Please install it with: pip install rdflib")
    sys.exit(1)

try:
    import jieba
except ImportError:
    print("ERROR: jieba is not installed.")
    print("Please install it with: pip install jieba")
    sys.exit(1)

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, project_root)

# Configuration
DATA_DIR = os.path.join(project_root, 'data', 'content_db')
ONTOLOGY_DIR = os.path.join(project_root, 'knowledge_graph', 'ontology')
KG_FILE = os.path.join(project_root, 'knowledge_graph', 'world_model_cwn.ttl')
GRAMMAR_FILE = os.path.join(DATA_DIR, 'chinese_grammar_knowledge_graph.json')
SCHEMA_FILE = os.path.join(ONTOLOGY_DIR, 'srs_schema.ttl')

# RDF Namespaces
SRS_KG = Namespace("http://srs4autism.com/schema/")
INST = Namespace("http://srs4autism.com/instance/")


def generate_slug(text):
    """Generate a URL-safe slug from text.
    
    Uses URL encoding for special characters to ensure valid URIs.
    """
    if not text:
        return "unknown"
    # URL encode the text to handle special characters, parentheses, quotes, etc.
    # This ensures valid URIs even with special characters
    encoded = quote(str(text), safe='')
    # Limit length to avoid extremely long URIs
    return encoded[:200]


def load_existing_words(graph):
    """
    Scan the graph and return a dict mapping Chinese words to their URIs.
    Returns: dict {word_text: word_uri}
    """
    print("Scanning existing words from Knowledge Graph...")
    word_map = {}
    
    # Query for all Word nodes
    query = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?word_uri ?word_text
    WHERE {
        ?word_uri a srs-kg:Word .
        ?word_uri srs-kg:text ?word_text .
    }
    """
    
    results = graph.query(query)
    for row in results:
        word_text = str(row.word_text)
        # Handle language-tagged literals
        if hasattr(word_text, 'value'):
            word_text = word_text.value
        word_map[word_text] = row.word_uri
    
    print(f"  Loaded {len(word_map)} existing words.")
    return word_map


def segment_chinese_sentence(sentence):
    """
    Segment a Chinese sentence into words using jieba.
    Returns a list of words (strings).
    """
    # Remove spaces and punctuation for segmentation
    clean_sentence = re.sub(r'[，。！？、\s]+', '', sentence)
    # Use jieba to segment
    words = list(jieba.cut(clean_sentence))
    # Filter out empty strings and single punctuation
    words = [w.strip() for w in words if w.strip() and len(w.strip()) > 0]
    return words


def populate_grammar():
    """
    Load existing KG, parse grammar JSON, and add all grammar
    and sentence nodes with relationships.
    """
    # Create or load graph
    graph = Graph()
    
    # Load existing KG if it exists
    if os.path.exists(KG_FILE):
        print(f"Loading existing Knowledge Graph from '{KG_FILE}'...")
        try:
            graph.parse(KG_FILE, format="turtle")
            print(f"  Loaded graph with {len(graph)} triples.")
        except Exception as e:
            print(f"  WARNING: Error loading existing graph: {e}")
            print("  Starting fresh...")
    else:
        print(f"  '{KG_FILE}' not found. Starting a new graph.")
    
    # Load schema
    if os.path.exists(SCHEMA_FILE):
        print(f"Loading ontology schema from '{SCHEMA_FILE}'...")
        try:
            graph.parse(SCHEMA_FILE, format="turtle")
            print("  Schema loaded successfully.")
        except Exception as e:
            print(f"  WARNING: Could not load schema: {e}")
    else:
        print(f"  WARNING: Schema file '{SCHEMA_FILE}' not found.")
    
    # Bind namespaces for clean output
    graph.bind("srs-kg", SRS_KG)
    graph.bind("srs-inst", INST)
    
    # Get map of existing words
    word_map = load_existing_words(graph)
    
    # Load grammar JSON
    if not os.path.exists(GRAMMAR_FILE):
        print(f"ERROR: Grammar file not found: {GRAMMAR_FILE}")
        sys.exit(1)
    
    print(f"\nLoading grammar data from '{GRAMMAR_FILE}'...")
    with open(GRAMMAR_FILE, 'r', encoding='utf-8') as f:
        grammar_data = json.load(f)
    
    print(f"Processing {len(grammar_data)} grammar points...")
    
    grammar_count = 0
    sentence_count = 0
    word_link_count = 0
    
    for i, point in enumerate(grammar_data):
        # Generate grammar point ID - ensure all parts are URL-safe
        level_slug = generate_slug(point['level'])
        gp_slug = generate_slug(point['grammar_point'])
        gp_id = f"gp-{level_slug}-{i+1:03d}-{gp_slug}"
        gp_uri = INST[gp_id]
        
        # Create GrammarPoint node
        graph.add((gp_uri, RDF.type, SRS_KG.GrammarPoint))
        graph.add((gp_uri, RDFS.label, Literal(point['grammar_point'], lang="en")))
        
        # Try to extract Chinese translation from structure, grammar_point name, or examples
        chinese_label = None
        structure = point.get('structure', '')
        gp_name = point.get('grammar_point', '')
        
        # Method 1: Extract from grammar_point name (often has Chinese in parentheses or quotes)
        chinese_match = re.search(r'[\u4e00-\u9fff]+', gp_name)
        if chinese_match:
            chinese_label = chinese_match.group(0)
        
        # Method 2: Extract from structure (often contains key Chinese words/phrases)
        if not chinese_label:
            chinese_chars = re.findall(r'[\u4e00-\u9fff]+', structure)
            if chinese_chars:
                # Filter out single common characters and use meaningful phrases
                meaningful = [c for c in chinese_chars if len(c) > 1 or c in ['的', '了', '吗', '呢', '啊']]
                if meaningful:
                    chinese_label = meaningful[0]
                elif chinese_chars:
                    chinese_label = chinese_chars[0]
        
        # Method 3: Extract from first example sentence (get key words)
        if not chinese_label:
            examples = point.get('examples', [])
            if examples and len(examples) > 0:
                first_example = examples[0].get('chinese', '')
                if first_example:
                    # Extract key Chinese words (2-4 characters) from the example
                    chinese_words = re.findall(r'[\u4e00-\u9fff]{2,4}', first_example)
                    if chinese_words:
                        chinese_label = chinese_words[0]  # Use first meaningful word
        
        # Add Chinese label if found
        if chinese_label:
            graph.add((gp_uri, RDFS.label, Literal(chinese_label, lang="zh")))
        
        graph.add((gp_uri, SRS_KG.cefrLevel, Literal(point['level'])))
        graph.add((gp_uri, SRS_KG.structure, Literal(point['structure'])))
        graph.add((gp_uri, SRS_KG.explanation, Literal(point['explanation'], lang="en")))
        
        grammar_count += 1
        
        # Process examples
        for j, ex in enumerate(point.get('examples', [])):
            chinese_text = ex.get('chinese', '').strip()
            
            # Skip examples that are just word definitions (no punctuation, very short)
            # Sentences should have punctuation or be multi-word
            if not chinese_text:
                continue
            # Skip if it's too short and has no punctuation or spaces (likely a word definition)
            has_punctuation = re.search(r'[，。！？、；：]', chinese_text)
            has_space = ' ' in chinese_text
            if not has_punctuation and not has_space and len(chinese_text) <= 2:
                continue
            
            # Generate sentence ID
            sent_id = f"sent-{gp_id}-{j+1:03d}"
            sent_uri = INST[sent_id]
            
            # Create Sentence node
            graph.add((sent_uri, RDF.type, SRS_KG.Sentence))
            graph.add((sent_uri, RDFS.label, Literal(chinese_text, lang="zh")))
            
            if ex.get('pinyin'):
                graph.add((sent_uri, SRS_KG.pinyin, Literal(ex['pinyin'])))
            
            if ex.get('english'):
                graph.add((sent_uri, SRS_KG.translationEN, Literal(ex['english'], lang="en")))
            
            # Link GrammarPoint to Sentence (hasExample)
            graph.add((gp_uri, SRS_KG.hasExample, sent_uri))
            
            # Link Sentence to GrammarPoint (demonstratesGrammar)
            graph.add((sent_uri, SRS_KG.demonstratesGrammar, gp_uri))
            
            sentence_count += 1
            
            # Link Sentence to Words (containsWord)
            # Segment the Chinese sentence
            words_in_sentence = segment_chinese_sentence(chinese_text)
            
            for word_text in words_in_sentence:
                # Check if word exists in our KG
                word_uri = word_map.get(word_text)
                if word_uri:
                    graph.add((sent_uri, SRS_KG.containsWord, word_uri))
                    word_link_count += 1
            
            # Progress indicator
            if (i + 1) % 50 == 0:
                print(f"  Processed {i + 1}/{len(grammar_data)} grammar points...")
    
    # Save the updated graph
    print(f"\nSaving updated graph...")
    print(f"  Grammar points added: {grammar_count}")
    print(f"  Sentences added: {sentence_count}")
    print(f"  Word links created: {word_link_count}")
    
    # Use utility function for backup and save
    try:
        from kg_utils import save_graph_with_backup
        if not save_graph_with_backup(graph, KG_FILE, create_timestamped=True):
            sys.exit(1)
    except ImportError:
        # Fallback if utility not available
        import shutil
        backup_file = f"{KG_FILE}.backup"
        if os.path.exists(KG_FILE):
            shutil.copy2(KG_FILE, backup_file)
            print(f"  ✅ Created backup: {backup_file}")
        
        try:
            graph.serialize(destination=KG_FILE, format="turtle")
            print(f"\n✅ Successfully saved updated graph to '{KG_FILE}'")
            print(f"   Total triples: {len(graph)}")
        except Exception as e:
            print(f"\n❌ ERROR saving graph: {e}")
            sys.exit(1)


if __name__ == "__main__":
    print("=" * 80)
    print("Chinese Grammar Knowledge Graph Populator")
    print("=" * 80)
    print()
    populate_grammar()
    print()
    print("Done!")
