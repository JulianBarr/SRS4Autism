#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Populate Chinese Knowledge Graph from CwnGraph (Chinese WordNet).

This script loads CwnGraph data and integrates it into the SRS4Autism
knowledge graph, creating a more complete world model with semantic relationships.
"""

import os
import sys
import pickle
import re
import csv
from collections import defaultdict
from urllib.parse import quote

try:
    from rdflib import Graph, Namespace, Literal, URIRef
    from rdflib.namespace import RDF, RDFS, SKOS, XSD
except ImportError:
    print("ERROR: rdflib is not installed.")
    print("Please install it with: pip install rdflib")
    sys.exit(1)

try:
    import chinese_converter
    HAS_CONVERTER = True
except ImportError:
    print("⚠️  WARNING: chinese-converter not installed.")
    print("   Traditional to Simplified conversion will be skipped.")
    print("   Install with: pip install chinese-converter")
    HAS_CONVERTER = False

try:
    from dragonmapper.transcriptions import zhuyin_to_pinyin
    HAS_DRAGONMAPPER = True
except ImportError:
    print("⚠️  WARNING: dragonmapper not installed.")
    print("   Bopomofo to Pinyin conversion will be skipped.")
    print("   Install with: pip install dragonmapper")
    HAS_DRAGONMAPPER = False

# We'll load the pickle file directly to avoid CwnGraph dependencies
# The pickle file contains (V, E, meta) where:
# - V: dict of nodes {node_id: node_data}
# - E: dict of edges {edge_id: edge_data}
# - meta: dict of metadata

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, project_root)

# Configuration
CWN_GRAPH_FILE = "/Users/maxent/src/CwnGraph/cwn-graph-v.2022.04.22.pyobj"
OUTPUT_FILE = os.path.join(project_root, 'knowledge_graph', 'world_model_cwn.ttl')
ONTOLOGY_FILE = os.path.join(project_root, 'knowledge_graph', 'ontology', 'srs_schema.ttl')
HSK_CSV = os.path.join(project_root, 'data', 'content_db', 'hsk_vocabulary.csv')

# RDF Namespaces
SRS_KG = Namespace("http://srs4autism.com/schema/")
RDF_NS = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")
RDFS_NS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
SKOS_NS = Namespace("http://www.w3.org/2004/02/skos/core#")


def generate_slug(text):
    """Generate a URL-safe slug from Chinese or English text."""
    if re.search(r'[\u4e00-\u9fff]', text):
        return quote(text, safe='')
    else:
        slug = re.sub(r'[^\w\s-]', '', text.lower())
        slug = re.sub(r'[-\s]+', '-', slug)
        return slug[:50]


def extract_characters(chinese_text):
    """Extract individual Chinese characters from text."""
    chars = re.findall(r'[\u4e00-\u9fff]', chinese_text)
    return chars


def convert_traditional_to_simplified(text):
    """Convert Traditional Chinese to Simplified Chinese."""
    if not HAS_CONVERTER or not text:
        return text
    try:
        return chinese_converter.to_simplified(text)
    except Exception:
        return text


def convert_bopomofo_to_pinyin(bopomofo):
    """Convert Bopomofo (Zhuyin) to Hanyu Pinyin."""
    if not HAS_DRAGONMAPPER or not bopomofo:
        return ""
    try:
        # Clean up bopomofo string (remove spaces, handle tone marks)
        cleaned = re.sub(r'\s+', '', bopomofo.strip())
        pinyin = zhuyin_to_pinyin(cleaned)
        return pinyin if pinyin else ""
    except Exception as e:
        return ""


def load_hsk_vocabulary(hsk_file):
    """Load HSK vocabulary data from CSV file.
    
    Expected CSV format:
    word,traditional,pinyin,hsk_level
    朋友,朋友,péngyou,1
    """
    hsk_data = {}  # simplified_word -> {hsk_level, pinyin, traditional}
    
    if not os.path.exists(hsk_file):
        print(f"⚠️  HSK vocabulary file not found: {hsk_file}")
        print(f"   Run 'python scripts/knowledge_graph/download_hsk.py' to download it.")
        return hsk_data
    
    try:
        with open(hsk_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Handle different column name variations
                word = row.get('word', row.get('simplified', row.get('chinese', ''))).strip()
                traditional = row.get('traditional', row.get('traditional_chinese', '')).strip()
                pinyin = row.get('pinyin', row.get('hanyu_pinyin', '')).strip()
                hsk_level = row.get('hsk_level', row.get('hsk', row.get('level', ''))).strip()
                
                if word:
                    # Try to convert hsk_level to integer
                    try:
                        hsk_level_int = int(hsk_level) if hsk_level else None
                    except ValueError:
                        hsk_level_int = None
                    
                    hsk_data[word] = {
                        'hsk_level': hsk_level_int,
                        'pinyin': pinyin,
                        'traditional': traditional if traditional else word
                    }
        
        print(f"✅ Loaded {len(hsk_data)} HSK vocabulary entries")
    except Exception as e:
        print(f"⚠️  ERROR loading HSK vocabulary: {e}")
    
    return hsk_data


def load_cwn_graph(cwn_file):
    """Load CwnGraph from pickle file."""
    print(f"Loading CwnGraph from: {cwn_file}")
    try:
        with open(cwn_file, "rb") as fin:
            data = pickle.load(fin)
            if len(data) == 2:
                V, E = data
                meta = {}
            else:
                V, E, meta = data
        
        print(f"✅ Loaded CwnGraph: {len(V)} nodes, {len(E)} edges")
        return V, E, meta
    except Exception as e:
        print(f"ERROR loading CwnGraph: {e}")
        sys.exit(1)


def create_character_node(graph, char, char_slug):
    """Create a Character node in the graph."""
    char_uri = SRS_KG[f"char-{char_slug}"]
    
    if (char_uri, RDF.type, SRS_KG.Character) in graph:
        return char_uri
    
    graph.add((char_uri, RDF.type, SRS_KG.Character))
    graph.add((char_uri, RDFS.label, Literal(char, lang="zh")))
    graph.add((char_uri, SRS_KG.glyph, Literal(char, lang="zh")))
    
    return char_uri


def create_word_node(graph, lemma_text, word_slug, pinyin=None, definition=None, 
                     char_uris=None, traditional=None, hsk_level=None):
    """Create a Word node and link it to character nodes."""
    word_uri = SRS_KG[f"word-{word_slug}"]
    
    if (word_uri, RDF.type, SRS_KG.Word) in graph:
        return word_uri
    
    graph.add((word_uri, RDF.type, SRS_KG.Word))
    graph.add((word_uri, RDFS.label, Literal(lemma_text, lang="zh")))
    graph.add((word_uri, SRS_KG.text, Literal(lemma_text, lang="zh")))
    
    # Add traditional Chinese if available and different
    # Note: If srs-kg:traditional property doesn't exist in ontology, 
    # add it to the schema or use a custom namespace
    if traditional and traditional != lemma_text:
        try:
            # Try to add traditional property (will fail silently if not in schema)
            graph.add((word_uri, SRS_KG.traditional, Literal(traditional, lang="zh")))
        except:
            # Fallback: store as a comment or annotation
            graph.add((word_uri, RDFS.comment, Literal(f"Traditional: {traditional}", lang="zh")))
    
    if pinyin:
        graph.add((word_uri, SRS_KG.pinyin, Literal(pinyin, lang="zh-Latn")))
    
    if definition:
        graph.add((word_uri, SRS_KG.definition, Literal(definition, lang="zh")))
    
    # Add HSK level if available
    if hsk_level is not None:
        graph.add((word_uri, SRS_KG.hskLevel, Literal(hsk_level, datatype=XSD.integer)))
    
    # Link to characters
    if char_uris:
        for char_uri in char_uris:
            graph.add((word_uri, SRS_KG.composedOf, char_uri))
            graph.add((word_uri, SRS_KG.requiresPrerequisite, char_uri))
    
    return word_uri


# Removed create_concept_from_sense - we create concepts directly in main()


def map_cwn_relation_to_ontology(cwn_rel_type, graph, source_concept, target_concept):
    """Map CWN relation types to ontology properties."""
    if cwn_rel_type == 'hypernym':
        # Target is more general, so source requires target as prerequisite
        graph.add((source_concept, SRS_KG.requiresPrerequisite, target_concept))
    elif cwn_rel_type == 'hyponym':
        # Reversed hypernym - source is more specific, so target requires source
        graph.add((target_concept, SRS_KG.requiresPrerequisite, source_concept))
    elif cwn_rel_type in ['synonym', 'is_synset', 'nearsynonym']:
        # Bidirectional synonym relationship
        graph.add((source_concept, SRS_KG.isSynonymOf, target_concept))
        graph.add((target_concept, SRS_KG.isSynonymOf, source_concept))
    elif cwn_rel_type == 'antonym':
        # Bidirectional antonym relationship
        graph.add((source_concept, SRS_KG.isAntonymOf, target_concept))
        graph.add((target_concept, SRS_KG.isAntonymOf, source_concept))
    # Note: meronym/holonym could be mapped to requiresPrerequisite in the future
    # For now, we skip generic and other relation types


def main():
    """Main function to populate the knowledge graph from CwnGraph."""
    print("=" * 80)
    print("Chinese Knowledge Graph Generator (CwnGraph Integration)")
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
            graph.parse(ONTOLOGY_FILE, format="turtle")
            print("✅ Ontology schema loaded successfully")
        except Exception as e:
            print(f"⚠️  WARNING: Could not parse ontology file: {e}")
            print("   Continuing without pre-loading schema...")
        print()
    
    # Load CwnGraph
    if not os.path.exists(CWN_GRAPH_FILE):
        print(f"ERROR: CwnGraph file not found: {CWN_GRAPH_FILE}")
        sys.exit(1)
    
    V, E, meta = load_cwn_graph(CWN_GRAPH_FILE)
    print()
    
    # Load HSK vocabulary
    print("Loading HSK vocabulary data...")
    hsk_data = load_hsk_vocabulary(HSK_CSV)
    print()
    
    # Track entities
    char_nodes = {}  # char -> char_uri
    word_nodes = {}  # lemma -> word_uri
    sense_concepts = {}  # sense_id -> concept_uri
    synset_concepts = {}  # synset_id -> concept_uri
    
    # Build lemma-to-sense mapping from edges
    lemma_to_senses = defaultdict(list)
    sense_to_lemmas = defaultdict(list)
    sense_definitions = {}  # sense_id -> definition
    sense_head_words = {}  # sense_id -> head_word
    
    # First pass: collect lemma-to-sense edges
    for edge_id, edge_data in E.items():
        source_id, target_id = edge_id
        edge_type = edge_data.get("edge_type", "")
        
        source_node = V.get(source_id, {})
        target_node = V.get(target_id, {})
        
        if edge_type == "has_sense":
            if source_node.get("node_type") == "lemma" and target_node.get("node_type") == "sense":
                lemma_to_senses[source_id].append(target_id)
                sense_to_lemmas[target_id].append(source_id)
        elif edge_type == "has_lemma":
            if source_node.get("node_type") == "sense" and target_node.get("node_type") == "lemma":
                sense_to_lemmas[source_id].append(target_id)
                lemma_to_senses[target_id].append(source_id)
    
    # Statistics
    stats = {
        'characters': 0,
        'words': 0,
        'senses': 0,
        'synsets': 0,
        'relations': 0
    }
    
    print("Processing CwnGraph data...")
    print()
    
    # Step 1: Extract all lemmas (words)
    print("Step 1: Processing lemmas (words)...")
    lemma_count = 0
    for node_id, node_data in V.items():
        if node_data.get("node_type") != "lemma":
            continue
        
        lemma_text = node_data.get("lemma", "") or node_data.get("lemma_type", "")
        if not lemma_text or lemma_text.strip() == "":
            continue
        
        # Remove trailing numbers (like "電腦_1")
        lemma_clean = re.sub(r'_\d+$', '', lemma_text)
        if not lemma_clean:
            continue
        
        # Convert traditional to simplified if needed
        lemma_simplified = convert_traditional_to_simplified(lemma_clean)
        traditional_form = lemma_clean if lemma_simplified != lemma_clean else None
        
        # Use simplified form for processing
        lemma_processed = lemma_simplified
        
        # Check for duplicates using processed form
        lemma_slug = generate_slug(lemma_processed)
        if lemma_processed in word_nodes:
            continue  # Already processed
        
        # Get pinyin from CwnGraph (might be bopomofo)
        cwn_pinyin_bopomofo = node_data.get("cwn_zhuyin", "") or node_data.get("zhuyin", "")
        
        # Convert bopomofo to pinyin if needed
        pinyin = ""
        if cwn_pinyin_bopomofo:
            # Try to convert bopomofo to pinyin
            pinyin = convert_bopomofo_to_pinyin(cwn_pinyin_bopomofo)
            if not pinyin:
                # If conversion failed, check if it's already pinyin
                # Bopomofo contains ㄅㄆㄇ characters
                if not re.search(r'[ㄅ-ㄩ]', cwn_pinyin_bopomofo):
                    pinyin = cwn_pinyin_bopomofo  # Already pinyin
        
        # Look up HSK data
        hsk_level = None
        hsk_pinyin = None
        hsk_traditional = None
        
        # Try matching with simplified form first
        if lemma_processed in hsk_data:
            hsk_info = hsk_data[lemma_processed]
            hsk_level = hsk_info.get('hsk_level')
            hsk_pinyin = hsk_info.get('pinyin')
            hsk_traditional = hsk_info.get('traditional')
        # Also try matching with original (traditional) form
        elif lemma_clean in hsk_data:
            hsk_info = hsk_data[lemma_clean]
            hsk_level = hsk_info.get('hsk_level')
            hsk_pinyin = hsk_info.get('pinyin')
            hsk_traditional = hsk_info.get('traditional')
        
        # Prefer HSK pinyin if available (more standardized)
        if hsk_pinyin:
            pinyin = hsk_pinyin
        
        # Use HSK traditional form if available
        if hsk_traditional and hsk_traditional != lemma_processed:
            traditional_form = hsk_traditional
        
        # Extract characters from simplified form for processing
        chars = extract_characters(lemma_processed)
        char_uris = []
        for char in chars:
            if char not in char_nodes:
                char_slug = generate_slug(char)
                char_uri = create_character_node(graph, char, char_slug)
                char_nodes[char] = char_uri
                stats['characters'] += 1
            char_uris.append(char_nodes[char])
        
        # Create word node with all metadata
        word_uri = create_word_node(
            graph, 
            lemma_processed,  # Use simplified as primary text
            lemma_slug, 
            pinyin=pinyin, 
            char_uris=char_uris,
            traditional=traditional_form,
            hsk_level=hsk_level
        )
        word_nodes[lemma_processed] = word_uri
        # Also map traditional form if different
        if traditional_form and traditional_form != lemma_processed:
            word_nodes[traditional_form] = word_uri
        stats['words'] += 1
        lemma_count += 1
        
        if lemma_count % 1000 == 0:
            print(f"  Processed {lemma_count} lemmas...")
    
    print(f"✅ Processed {lemma_count} lemmas")
    print()
    
    # Step 2: Extract senses and create concepts
    print("Step 2: Processing senses (word meanings)...")
    sense_count = 0
    for node_id, node_data in V.items():
        if node_data.get("node_type") != "sense":
            continue
        
        definition = node_data.get("def", "") or node_data.get("definition", "")
        if not definition:
            continue
        
        # Get the lemma(s) for this sense
        lemma_ids = sense_to_lemmas.get(node_id, [])
        head_word = ""
        if lemma_ids:
            first_lemma_id = lemma_ids[0]
            first_lemma = V.get(first_lemma_id, {})
            lemma_text = first_lemma.get("lemma", "") or first_lemma.get("lemma_type", "")
            lemma_clean = re.sub(r'_\d+$', '', lemma_text)
            # Convert to simplified for matching
            head_word = convert_traditional_to_simplified(lemma_clean)
        
        # Store sense info
        sense_definitions[node_id] = definition
        sense_head_words[node_id] = head_word
        
        # Create concept from sense
        concept_slug = generate_slug(f"{head_word}-{node_id}" if head_word else f"sense-{node_id}")
        concept_uri = SRS_KG[f"concept-{concept_slug}"]
        
        if (concept_uri, RDF.type, SRS_KG.Concept) not in graph:
            graph.add((concept_uri, RDF.type, SRS_KG.Concept))
            if definition:
                label = definition[:100]  # Limit length
                graph.add((concept_uri, RDFS.label, Literal(f"concept:{label}", lang="zh")))
                graph.add((concept_uri, RDFS.comment, Literal(definition, lang="zh")))
            elif head_word:
                graph.add((concept_uri, RDFS.label, Literal(f"concept:{head_word}", lang="zh")))
        
        sense_concepts[node_id] = concept_uri
        
        # Link word to concept if we have the word (try both simplified and traditional)
        word_uri = None
        if head_word in word_nodes:
            word_uri = word_nodes[head_word]
        # Also try original traditional form if simplified didn't match
        elif lemma_ids:
            first_lemma_id = lemma_ids[0]
            first_lemma = V.get(first_lemma_id, {})
            lemma_text = first_lemma.get("lemma", "") or first_lemma.get("lemma_type", "")
            lemma_clean = re.sub(r'_\d+$', '', lemma_text)
            if lemma_clean in word_nodes:
                word_uri = word_nodes[lemma_clean]
        
        if word_uri:
            graph.add((word_uri, SRS_KG.means, concept_uri))
        
        sense_count += 1
        stats['senses'] += 1
        
        if sense_count % 1000 == 0:
            print(f"  Processed {sense_count} senses...")
    
    print(f"✅ Processed {sense_count} senses")
    print()
    
    # Step 3: Extract synsets
    print("Step 3: Processing synsets...")
    synset_count = 0
    for node_id, node_data in V.items():
        if node_data.get("node_type") != "synset":
            continue
        
        gloss = node_data.get("gloss", "") or node_data.get("definition", "")
        
        concept_slug = generate_slug(f"synset-{node_id}")
        concept_uri = SRS_KG[f"concept-{concept_slug}"]
        
        if (concept_uri, RDF.type, SRS_KG.Concept) not in graph:
            graph.add((concept_uri, RDF.type, SRS_KG.Concept))
            if gloss:
                graph.add((concept_uri, RDFS.label, Literal(f"synset:{gloss[:50]}", lang="zh")))
                graph.add((concept_uri, RDFS.comment, Literal(gloss, lang="zh")))
            else:
                graph.add((concept_uri, RDFS.label, Literal(f"synset:{node_id}", lang="zh")))
        
        synset_concepts[node_id] = concept_uri
        synset_count += 1
        stats['synsets'] += 1
    
    print(f"✅ Processed {synset_count} synsets")
    print()
    
    # Step 4: Extract relationships
    print("Step 4: Processing relationships...")
    relation_count = 0
    
    for edge_id, edge_data in E.items():
        source_id, target_id = edge_id
        edge_type = edge_data.get("edge_type", "")
        
        if not edge_type:
            continue
        
        source_node = V.get(source_id, {})
        target_node = V.get(target_id, {})
        
        if not source_node or not target_node:
            continue
        
        source_type = source_node.get("node_type")
        target_type = target_node.get("node_type")
        
        # Map sense-to-sense relations to concept-to-concept
        if source_type == "sense" and target_type == "sense":
            source_concept = sense_concepts.get(source_id)
            target_concept = sense_concepts.get(target_id)
            
            if source_concept and target_concept and source_concept != target_concept:
                map_cwn_relation_to_ontology(edge_type, graph, source_concept, target_concept)
                relation_count += 1
        
        # Map synset-to-synset relations
        elif source_type == "synset" and target_type == "synset":
            source_concept = synset_concepts.get(source_id)
            target_concept = synset_concepts.get(target_id)
            
            if source_concept and target_concept and source_concept != target_concept:
                map_cwn_relation_to_ontology(edge_type, graph, source_concept, target_concept)
                relation_count += 1
        
        # Map sense-to-synset relations
        elif source_type == "sense" and target_type == "synset":
            source_concept = sense_concepts.get(source_id)
            target_concept = synset_concepts.get(target_id)
            
            if source_concept and target_concept and edge_type in ['is_synset', 'has_synset']:
                graph.add((source_concept, SRS_KG.isSynonymOf, target_concept))
                relation_count += 1
        
        # Map synset-to-sense relations (reverse)
        elif source_type == "synset" and target_type == "sense":
            source_concept = synset_concepts.get(source_id)
            target_concept = sense_concepts.get(target_id)
            
            if source_concept and target_concept and edge_type in ['is_synset', 'has_synset']:
                graph.add((target_concept, SRS_KG.isSynonymOf, source_concept))
                relation_count += 1
        
        if relation_count > 0 and relation_count % 10000 == 0:
            print(f"  Processed {relation_count} relations...")
    
    print(f"✅ Processed {relation_count} relations")
    stats['relations'] = relation_count
    print()
    
    # Summary
    print("=" * 80)
    print("Knowledge Graph Generation Complete!")
    print("=" * 80)
    print(f"\nStatistics:")
    print(f"  - Characters: {stats['characters']}")
    print(f"  - Words: {stats['words']}")
    print(f"  - Senses (Concepts): {stats['senses']}")
    print(f"  - Synsets: {stats['synsets']}")
    print(f"  - Relations: {stats['relations']}")
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
    print("CwnGraph integration complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()

