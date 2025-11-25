#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Populate English Vocabulary Knowledge Graph from EVP (English Vocabulary Profile) data.

This script reads English vocabulary with CEFR levels and generates a knowledge graph
in Turtle format conforming to the SRS4Autism ontology schema.

Data Sources:
- EVP (English Vocabulary Profile) - CEFR levels A1-C2
- Can also accept CSV/JSON input files with word, definition, cefr_level, pos columns
"""

import os
import sys
import csv
import json
import re
import requests
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
OUTPUT_FILE = os.path.join(project_root, 'knowledge_graph', 'world_model_english.ttl')
KG_FILE = os.path.join(project_root, 'knowledge_graph', 'world_model_cwn.ttl')  # Existing Chinese KG

# CEFR-J dataset location
CEFRJ_DIR = os.path.join(project_root, '..', 'olp-en-cefrj')
CEFRJ_VOCAB_CSV = os.path.join(CEFRJ_DIR, 'cefrj-vocabulary-profile-1.5.csv')
OCTANOVE_VOCAB_CSV = os.path.join(CEFRJ_DIR, 'octanove-vocabulary-profile-c1c2-1.0.csv')

# CSV/JSON input files (fallback)
ENGLISH_VOCAB_CSV = os.path.join(DATA_DIR, 'english_vocab_evp.csv')
ENGLISH_VOCAB_JSON = os.path.join(DATA_DIR, 'english_vocab_evp.json')
COCA_CSV = os.path.join(DATA_DIR, 'coca_20000.csv')
CONCRETENESS_FILE = os.path.join(DATA_DIR, 'Concreteness_ratings_Brysbaert_et_al_BRM.txt')
ONTOLOGY_FILE = os.path.join(ONTOLOGY_DIR, 'srs_schema.ttl')

# RDF Namespaces
SRS_KG = Namespace("http://srs4autism.com/schema/")
RDF_NS = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")
RDFS_NS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
SKOS_NS = Namespace("http://www.w3.org/2004/02/skos/core#")


def generate_slug(text):
    """Generate a URL-safe slug from English text."""
    if not text:
        return ""
    # Convert to lowercase, replace spaces/special chars with hyphens
    slug = re.sub(r'[^\w\s-]', '', text.lower())
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug[:50]  # Limit length


def normalize_cefr_level(level):
    """Normalize CEFR level to standard format (A1, A2, B1, B2, C1, C2)."""
    if not level:
        return None
    level = str(level).strip().upper()
    # Handle variations like "A1", "a1", "CEFR A1", etc.
    match = re.search(r'([A-C])([12])', level)
    if match:
        return f"{match.group(1)}{match.group(2)}"
    return None


def create_word_node(graph, word_text, word_slug, definition=None, cefr_level=None, 
                     pos=None, concreteness=None):
    """Create an English Word node in the graph."""
    word_uri = SRS_KG[f"word-en-{word_slug}"]
    
    # Avoid duplicates
    if (word_uri, RDF.type, SRS_KG.Word) in graph:
        return word_uri
    
    graph.add((word_uri, RDF.type, SRS_KG.Word))
    graph.add((word_uri, RDFS.label, Literal(word_text, lang="en")))
    graph.add((word_uri, SRS_KG.text, Literal(word_text, lang="en")))
    
    if definition:
        graph.add((word_uri, SRS_KG.definition, Literal(definition, lang="en")))
    
    if cefr_level:
        normalized_level = normalize_cefr_level(cefr_level)
        if normalized_level:
            graph.add((word_uri, SRS_KG.cefrLevel, Literal(normalized_level)))
    
    if pos:
        graph.add((word_uri, SRS_KG.partOfSpeech, Literal(pos, lang="en")))
    
    if concreteness:
        graph.add((word_uri, SRS_KG.concreteness, Literal(str(concreteness))))
    
    return word_uri


def create_concept_node(graph, concept_text, concept_slug):
    """Create a Concept node based on English word/definition."""
    concept_uri = SRS_KG[f"concept-{concept_slug}"]
    
    # Avoid duplicates
    if (concept_uri, RDF.type, SRS_KG.Concept) in graph:
        return concept_uri
    
    graph.add((concept_uri, RDF.type, SRS_KG.Concept))
    graph.add((concept_uri, RDFS.label, Literal(f"concept:{concept_text}", lang="en")))
    graph.add((concept_uri, RDFS.comment, Literal(concept_text, lang="en")))
    
    return concept_uri


def load_cefrj_csv(csv_file):
    """Load vocabulary data from CEFR-J CSV format.
    
    Expected columns: headword, pos, CEFR, ...
    """
    words = []
    
    if not os.path.exists(csv_file):
        print(f"⚠️  CEFR-J CSV file not found: {csv_file}")
        return words
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                headword = row.get('headword', '').strip()
                pos = row.get('pos', '').strip()
                cefr_level = row.get('CEFR', '').strip()
                
                if headword and cefr_level:
                    words.append({
                        'word': headword,
                        'definition': '',  # CEFR-J doesn't include definitions
                        'cefr_level': cefr_level,
                        'pos': pos,
                        'concreteness': None
                    })
    except Exception as e:
        print(f"ERROR reading CEFR-J CSV {csv_file}: {e}")
    
    return words


def load_csv_data(csv_file):
    """Load vocabulary data from generic CSV file.
    
    Expected columns: word, definition, cefr_level, pos (optional), concreteness (optional)
    Or CEFR-J format: headword, pos, CEFR, ...
    """
    words = []
    
    if not os.path.exists(csv_file):
        print(f"⚠️  CSV file not found: {csv_file}")
        return words
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            # Peek at first line to detect format
            first_line = f.readline()
            f.seek(0)
            
            reader = csv.DictReader(f)
            
            # Check if it's CEFR-J format
            if 'headword' in reader.fieldnames and 'CEFR' in reader.fieldnames:
                return load_cefrj_csv(csv_file)
            
            # Otherwise, use generic format
            for row in reader:
                word = row.get('word', row.get('Word', '')).strip()
                definition = row.get('definition', row.get('Definition', row.get('meaning', ''))).strip()
                cefr_level = row.get('cefr_level', row.get('CEFR', row.get('level', ''))).strip()
                pos = row.get('pos', row.get('POS', row.get('part_of_speech', ''))).strip()
                concreteness = row.get('concreteness', row.get('Concreteness', '')).strip()
                
                if word:
                    words.append({
                        'word': word,
                        'definition': definition,
                        'cefr_level': cefr_level,
                        'pos': pos,
                        'concreteness': float(concreteness) if concreteness and concreteness.replace('.', '').isdigit() else None
                    })
    except Exception as e:
        print(f"ERROR reading {csv_file}: {e}")
    
    return words


def load_json_data(json_file):
    """Load vocabulary data from JSON file.
    
    Expected format: [{"word": "...", "definition": "...", "cefr_level": "...", ...}, ...]
    """
    words = []
    
    if not os.path.exists(json_file):
        print(f"⚠️  JSON file not found: {json_file}")
        return words
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                for item in data:
                    word = item.get('word', '').strip()
                    if word:
                        words.append({
                            'word': word,
                            'definition': item.get('definition', item.get('meaning', '')).strip(),
                            'cefr_level': item.get('cefr_level', item.get('cefr', item.get('level', ''))).strip(),
                            'pos': item.get('pos', item.get('part_of_speech', '')).strip(),
                            'concreteness': item.get('concreteness')
                        })
    except Exception as e:
        print(f"ERROR reading {json_file}: {e}")
    
    return words


def download_evp_sample():
    """
    Attempt to download or provide instructions for EVP data.
    
    Note: EVP data may require manual download or API access.
    This function provides a template for future implementation.
    """
    print("ℹ️  EVP data download not yet implemented.")
    print("   Please download EVP data manually from:")
    print("   https://www.englishprofile.org/wordlists")
    print("   Or provide a CSV/JSON file with the following columns:")
    print("   - word: The English word")
    print("   - definition: Word definition")
    print("   - cefr_level: CEFR level (A1, A2, B1, B2, C1, C2)")
    print("   - pos: Part of speech (optional)")
    print("   - concreteness: Concreteness rating 1-5 (optional)")
    return []


def load_coca_csv(coca_file):
    """
    Load COCA word list from CSV file.
    
    Expected format: word,rank,frequency,pos
    Returns list of dicts with word, rank, frequency, pos
    """
    words = []
    
    if not os.path.exists(coca_file):
        return words
    
    try:
        with open(coca_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                word = (
                    row.get('word', '') or 
                    row.get('Word', '') or 
                    row.get('lemma', '') or
                    row.get('Lemma', '')
                ).strip()
                
                rank_str = (
                    row.get('rank', '') or
                    row.get('Rank', '') or
                    row.get('#', '')
                ).strip()
                
                freq_str = (
                    row.get('frequency', '') or
                    row.get('Frequency', '') or
                    row.get('freq', '') or
                    row.get('Freq', '')
                ).strip()
                
                pos = (
                    row.get('pos', '') or
                    row.get('POS', '') or
                    row.get('part_of_speech', '')
                ).strip()
                
                if not word:
                    continue
                
                try:
                    rank = int(rank_str) if rank_str and rank_str.replace(',', '').isdigit() else None
                    frequency = int(freq_str.replace(',', '')) if freq_str and freq_str.replace(',', '').replace('.', '').isdigit() else None
                except:
                    rank = None
                    frequency = None
                
                words.append({
                    'word': word,
                    'rank': rank,
                    'frequency': frequency,
                    'pos': pos,
                    'definition': '',  # COCA doesn't provide definitions
                    'cefr_level': None,  # Will be estimated from rank
                    'concreteness': None
                })
    
    except Exception as e:
        print(f"⚠️  Error reading COCA file {coca_file}: {e}")
    
    return words


def estimate_cefr_from_rank(rank):
    """Estimate CEFR level from COCA rank."""
    if rank is None:
        return None
    
    if rank <= 1000:
        return "A2"
    elif rank <= 5000:
        return "B1"
    elif rank <= 10000:
        return "B2"
    elif rank <= 20000:
        return "C1"
    else:
        return "C2"


def load_concreteness_data(concreteness_file):
    """
    Load concreteness ratings from Brysbaert et al. dataset.
    
    Expected format: Tab-separated with columns:
    Word, Bigram, Conc.M, Conc.SD, Unknown, Total, Percent_known, SUBTLEX, Dom_Pos
    
    Returns dict mapping word_lower -> concreteness_score (float 0-5)
    """
    concreteness_map = {}
    
    if not os.path.exists(concreteness_file):
        return concreteness_map
    
    try:
        with open(concreteness_file, 'r', encoding='utf-8') as f:
            # Skip header line
            header = f.readline()
            
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                # Tab-separated format
                parts = line.split('\t')
                if len(parts) < 3:
                    continue
                
                word = parts[0].strip()
                conc_m_str = parts[2].strip()  # Conc.M column
                
                if not word or not conc_m_str:
                    continue
                
                try:
                    concreteness = float(conc_m_str)
                    # Store as lowercase for matching
                    word_lower = word.lower()
                    # If word already exists, keep the first (or could average)
                    if word_lower not in concreteness_map:
                        concreteness_map[word_lower] = concreteness
                except (ValueError, IndexError):
                    continue
    
    except Exception as e:
        print(f"⚠️  Error reading concreteness file {concreteness_file}: {e}")
    
    return concreteness_map


def main():
    """Main function to populate the English vocabulary knowledge graph."""
    print("=" * 80)
    print("English Vocabulary Knowledge Graph Generator (EVP/CEFR)")
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
    else:
        print(f"⚠️  WARNING: Ontology file not found: {ONTOLOGY_FILE}")
        print("   The schema will be defined in the output file.")
        print()
    
    # Optionally merge with existing Chinese KG
    merge_existing = False
    if os.path.exists(KG_FILE) and input("Merge with existing Chinese KG? (y/n): ").lower() == 'y':
        print(f"Loading existing knowledge graph from: {KG_FILE}")
        try:
            existing_graph = Graph()
            existing_graph.parse(KG_FILE, format="turtle")
            # Merge graphs
            for triple in existing_graph:
                graph.add(triple)
            print(f"✅ Merged {len(existing_graph)} triples from existing KG")
            merge_existing = True
        except Exception as e:
            print(f"⚠️  WARNING: Could not load existing KG: {e}")
            print("   Continuing with new graph only...")
        print()
    
    # Load vocabulary data
    print("Loading vocabulary data...")
    all_words = []
    word_map = {}  # word_lower -> word_data (for deduplication and merging)
    
    # Step 1: Try CEFR-J dataset first (primary source with CEFR levels)
    if os.path.exists(CEFRJ_VOCAB_CSV):
        words_cefrj = load_cefrj_csv(CEFRJ_VOCAB_CSV)
        print(f"  ✅ Loaded {len(words_cefrj)} words from CEFR-J vocabulary profile")
        for word_data in words_cefrj:
            word_lower = word_data['word'].lower()
            word_map[word_lower] = word_data  # CEFR-J takes precedence
        all_words.extend(words_cefrj)
    
    # Try Octanove C1/C2 supplement
    if os.path.exists(OCTANOVE_VOCAB_CSV):
        words_octanove = load_cefrj_csv(OCTANOVE_VOCAB_CSV)
        print(f"  ✅ Loaded {len(words_octanove)} words from Octanove C1/C2 profile")
        for word_data in words_octanove:
            word_lower = word_data['word'].lower()
            # Only add if not already in map (CEFR-J takes precedence)
            if word_lower not in word_map:
                word_map[word_lower] = word_data
                all_words.append(word_data)
            else:
                # Update existing with Octanove CEFR level if CEFR-J didn't have one
                if not word_map[word_lower].get('cefr_level') and word_data.get('cefr_level'):
                    word_map[word_lower]['cefr_level'] = word_data['cefr_level']
    
    # Step 2: Load COCA data to complement CEFR-J with frequency info
    coca_added = 0
    coca_frequency_added = 0
    if os.path.exists(COCA_CSV):
        words_coca = load_coca_csv(COCA_CSV)
        print(f"  ✅ Loaded {len(words_coca)} words from COCA 20000")
        
        # Process COCA words
        for word_data in words_coca:
            word_lower = word_data['word'].lower()
            
            # Add new COCA words not in CEFR-J
            if word_lower not in word_map:
                # Estimate CEFR level from rank
                estimated_cefr = estimate_cefr_from_rank(word_data.get('rank'))
                word_data['cefr_level'] = estimated_cefr
                word_map[word_lower] = word_data
                all_words.append(word_data)
                coca_added += 1
            else:
                # Add frequency info to existing CEFR-J words
                word_map[word_lower]['rank'] = word_data.get('rank')
                word_map[word_lower]['frequency'] = word_data.get('frequency')
                # Add POS if missing
                if not word_map[word_lower].get('pos') and word_data.get('pos'):
                    word_map[word_lower]['pos'] = word_data['pos']
                coca_frequency_added += 1
        
        if coca_added > 0:
            print(f"    📊 Added {coca_added} new words from COCA (not in CEFR-J)")
        if coca_frequency_added > 0:
            print(f"    📊 Added frequency info to {coca_frequency_added} existing CEFR-J words")
    
    # Step 3: Load concreteness data and match to words
    concreteness_added = 0
    if os.path.exists(CONCRETENESS_FILE):
        concreteness_map = load_concreteness_data(CONCRETENESS_FILE)
        print(f"  ✅ Loaded {len(concreteness_map)} concreteness ratings")
        
        # Match concreteness to words in word_map
        for word_lower, word_data in word_map.items():
            if word_lower in concreteness_map:
                word_data['concreteness'] = concreteness_map[word_lower]
                concreteness_added += 1
        
        if concreteness_added > 0:
            print(f"    📊 Added concreteness ratings to {concreteness_added} words")
    
    # Step 4: Update all_words with merged data
    all_words = []
    for word_lower, word_data in word_map.items():
        all_words.append(word_data)
    
    # Try fallback CSV
    if os.path.exists(ENGLISH_VOCAB_CSV):
        words_csv = load_csv_data(ENGLISH_VOCAB_CSV)
        if words_csv:
            print(f"  ✅ Loaded {len(words_csv)} words from {os.path.basename(ENGLISH_VOCAB_CSV)}")
            for word_data in words_csv:
                word_lower = word_data['word'].lower()
                if word_lower not in word_map:
                    word_map[word_lower] = word_data
                    all_words.append(word_data)
    
    # Try JSON
    if os.path.exists(ENGLISH_VOCAB_JSON):
        words_json = load_json_data(ENGLISH_VOCAB_JSON)
        if words_json:
            print(f"  ✅ Loaded {len(words_json)} words from {os.path.basename(ENGLISH_VOCAB_JSON)}")
            for word_data in words_json:
                word_lower = word_data['word'].lower()
                if word_lower not in word_map:
                    word_map[word_lower] = word_data
                    all_words.append(word_data)
    
    # If no data found, try to download or provide instructions
    if not all_words:
        print("  ⚠️  No vocabulary data files found.")
        print("  Attempting to download EVP data...")
        evp_words = download_evp_sample()
        if evp_words:
            all_words.extend(evp_words)
    
    if not all_words:
        print("\n❌ ERROR: No vocabulary data found.")
        print(f"   Please create one of the following files:")
        print(f"   - {ENGLISH_VOCAB_CSV}")
        print(f"   - {ENGLISH_VOCAB_JSON}")
        print("\n   Expected CSV format:")
        print("   word,definition,cefr_level,pos,concreteness")
        print("   cat,a small domesticated carnivorous mammal,A1,noun,4.8")
        print("   dog,a domesticated carnivorous mammal,A1,noun,4.9")
        sys.exit(1)
    
    print(f"\nTotal words to process: {len(all_words)}")
    
    # Count by CEFR level
    cefr_counts = defaultdict(int)
    for word_data in all_words:
        level = normalize_cefr_level(word_data.get('cefr_level', ''))
        if level:
            cefr_counts[level] += 1
    
    if cefr_counts:
        print("\nCEFR Level Distribution:")
        for level in ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']:
            count = cefr_counts.get(level, 0)
            if count > 0:
                print(f"  {level}: {count} words")
    print()
    
    # Track concepts to avoid duplicates
    concept_map = {}  # word/definition -> concept_uri
    
    # Process words
    print("Generating knowledge graph triples...")
    word_count = 0
    concept_count = 0
    
    for word_data in all_words:
        word_text = word_data['word']
        definition = word_data.get('definition', '')
        cefr_level = word_data.get('cefr_level', '')
        pos = word_data.get('pos', '')
        concreteness = word_data.get('concreteness')
        
        # Generate slugs
        word_slug = generate_slug(word_text)
        concept_key = definition if definition else word_text.lower()
        concept_slug = generate_slug(concept_key)
        
        # Create word node
        word_uri = create_word_node(
            graph, word_text, word_slug, 
            definition=definition, 
            cefr_level=cefr_level,
            pos=pos,
            concreteness=concreteness
        )
        word_count += 1
        
        # Create concept node (one per unique concept)
        if concept_slug not in concept_map:
            concept_uri = create_concept_node(graph, definition or word_text, concept_slug)
            concept_map[concept_slug] = concept_uri
            concept_count += 1
        else:
            concept_uri = concept_map[concept_slug]
        
        # Link word to concept
        graph.add((word_uri, SRS_KG.means, concept_uri))
        
        # Progress indicator
        if word_count % 100 == 0:
            print(f"  Processed {word_count} words...")
    
    print(f"\n✅ Generated knowledge graph:")
    print(f"   - {word_count} English words")
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
        triple_count = len(graph)
        print(f"✅ Successfully wrote {file_size:,} bytes ({triple_count:,} triples) to {OUTPUT_FILE}")
    except Exception as e:
        print(f"❌ ERROR writing output file: {e}")
        sys.exit(1)
    
    print()
    print("=" * 80)
    print("Knowledge graph generation complete!")
    print("=" * 80)
    print(f"\nNext steps:")
    print(f"  1. Review the output: {OUTPUT_FILE}")
    if merge_existing:
        print(f"  2. The graph includes both Chinese and English vocabulary")
    else:
        print(f"  2. To merge with Chinese KG, run with existing KG file")
    print(f"  3. Load into Fuseki for querying")
    print(f"  4. Use in recommender engine with CEFR levels")


if __name__ == "__main__":
    main()

