#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Populate Knowledge Graph with Visual Images from Anki Packages.

This script extracts visual images from Anki .apkg files and links them
to concepts in the knowledge graph. Images are extracted from the "front"
field of Anki cards and matched to concepts via English words.

Anki packages:
- English__Vocabulary__1. Basic.apkg
- English__Vocabulary__2. Level 2.apkg
"""

import os
import sys
import sqlite3
import zipfile
import re
import shutil
import hashlib
import time
from pathlib import Path
from urllib.parse import quote
from collections import defaultdict

try:
    from rdflib import Graph, Namespace, Literal, URIRef, BNode
    from rdflib.namespace import RDF, RDFS, XSD
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
KG_FILE = os.path.join(project_root, 'knowledge_graph', 'world_model_cwn.ttl')
SCHEMA_FILE = os.path.join(ONTOLOGY_DIR, 'srs_schema.ttl')
MEDIA_DIR = os.path.join(project_root, 'media', 'visual_images')

# STORAGE APPROACH:
# - Images are stored as FILES in the filesystem (media/visual_images/)
# - Only METADATA (file paths) are stored in the knowledge graph (Jena/Fuseki)
# - This is efficient and scalable - binary data is NOT embedded in RDF
# - To serve images via HTTP, you may need to add a static file endpoint in the backend

# Anki package files
ANKI_PACKAGES = [
    os.path.join(DATA_DIR, 'English__Vocabulary__1. Basic.apkg'),
    os.path.join(DATA_DIR, 'English__Vocabulary__2. Level 2.apkg'),
]

# RDF Namespaces
SRS_KG = Namespace("http://srs4autism.com/schema/")
INST = Namespace("http://srs4autism.com/instance/")


def extract_apkg(apkg_path, extract_dir):
    """
    Extract an Anki .apkg file (which is a zip file) to a temporary directory.
    Returns the path to the extracted directory.
    """
    if not os.path.exists(apkg_path):
        print(f"⚠️  Package not found: {apkg_path}")
        return None
    
    print(f"Extracting {os.path.basename(apkg_path)}...")
    try:
        with zipfile.ZipFile(apkg_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        print(f"  ✅ Extracted to {extract_dir}")
        return extract_dir
    except Exception as e:
        print(f"  ❌ Error extracting package: {e}")
        return None


def read_anki_database(db_path):
    """
    Read the Anki SQLite database and extract card data.
    Returns a list of dictionaries with card information.
    
    Anki database structure:
    - 'col' table contains 'models' as JSON text
    - 'notes' table contains notes with 'flds' (fields separated by \x1f)
    - 'mid' in notes refers to model ID in the models JSON
    
    Note: .anki21b files are zlib-compressed and need to be decompressed first.
    """
    if not os.path.exists(db_path):
        print(f"⚠️  Database not found: {db_path}")
        return []
    
    cards = []
    try:
        import json
        import zlib
        import tempfile
        
        # Check if file is compressed (.anki21b files use a custom compression format)
        # For now, we'll try to use the .anki2 file if .anki21b fails
        # The .anki21b format appears to use a proprietary compression that's not standard zlib
        with open(db_path, 'rb') as f:
            first_bytes = f.read(16)
            is_sqlite = first_bytes.startswith(b'SQLite format 3')
            is_compressed = first_bytes.startswith(b'(\xb5/\xfd')  # Custom Anki compression
        
        if is_sqlite:
            # Already a SQLite database
            tmp_db_path = db_path
        elif is_compressed:
            # .anki21b files use a custom compression format that's not easily decompressible
            # Try to find and use the .anki2 file instead
            db_dir = os.path.dirname(db_path)
            alt_db_path = os.path.join(db_dir, 'collection.anki2')
            if os.path.exists(alt_db_path):
                print(f"  ⚠️  .anki21b uses custom compression, trying .anki2 file instead...")
                # Check if .anki2 is actually a database
                with open(alt_db_path, 'rb') as f:
                    alt_first_bytes = f.read(16)
                    if alt_first_bytes.startswith(b'SQLite format 3'):
                        tmp_db_path = alt_db_path
                        print(f"  ✅ Using .anki2 database")
                    else:
                        print(f"  ❌ .anki2 file is also not a valid database")
                        return []
            else:
                print(f"  ❌ Cannot decompress .anki21b and no valid .anki2 file found")
                print(f"  ⚠️  .anki21b uses custom compression format (not standard zlib)")
                print(f"  ⚠️  This format may require Anki's proprietary libraries to read")
                return []
        else:
            # Unknown format, try to open as SQLite anyway
            tmp_db_path = db_path
        
        try:
            conn = sqlite3.connect(tmp_db_path)
            cursor = conn.cursor()
            
            # Get models from 'col' table (stored as JSON)
            cursor.execute("SELECT models FROM col LIMIT 1")
            row = cursor.fetchone()
            if not row or not row[0]:
                print(f"  ⚠️  No models found in col table")
                conn.close()
                return []
            
            models_json = json.loads(row[0])
            model_fields = {}
            model_names = {}
            
            # Parse models JSON to get field names for each model
            for model_id_str, model_data in models_json.items():
                model_id = int(model_id_str)
                model_name = model_data.get('name', 'Unknown')
                model_names[model_id] = model_name
                
                # Get field names from 'flds' array in model
                fields = model_data.get('flds', [])
                field_names = [f.get('name', f'field_{i}') for i, f in enumerate(fields)]
                model_fields[model_id] = field_names
            
            print(f"  Found {len(model_fields)} note models")
            
            # Query to get all notes
            cursor.execute("""
                SELECT id, mid, flds 
                FROM notes
            """)
            rows = cursor.fetchall()
            
            # Parse each note
            for note_id, model_id, flds in rows:
                if not flds:
                    continue
                
                # Fields are separated by \x1f (unit separator)
                field_values = flds.split('\x1f')
                field_names = model_fields.get(model_id, [])
                
                # Create a dict mapping field names to values
                card_data = {
                    'note_id': note_id,
                    'model_id': model_id,
                    'model_name': model_names.get(model_id, 'Unknown'),
                }
                
                # Map field values to names
                for i, value in enumerate(field_values):
                    if i < len(field_names):
                        card_data[field_names[i]] = value
                    else:
                        card_data[f'field_{i}'] = value
                
                cards.append(card_data)
            
            conn.close()
            print(f"  ✅ Loaded {len(cards)} cards from database")
            return cards
        finally:
            # Clean up temporary file if we created one
            if is_compressed and tmp_db_path != db_path and os.path.exists(tmp_db_path):
                os.unlink(tmp_db_path)
        
    except Exception as e:
        print(f"  ❌ Error reading database: {e}")
        import traceback
        traceback.print_exc()
        return []


def extract_images_from_html(html_content):
    """
    Extract image references from HTML content.
    Returns a list of image filenames found in <img> tags.
    
    Handles both quoted and unquoted src attributes:
    - <img src="filename.png"> (with quotes)
    - <img src=filename.png /> (without quotes)
    - <img src='filename.png'> (single quotes)
    """
    if not html_content:
        return []
    
    images = []
    
    # Pattern 1: Match quoted src (with single or double quotes)
    pattern_quoted = r'<img[^>]*src=["\']([^"\']+)["\']'
    matches_quoted = re.findall(pattern_quoted, html_content, re.IGNORECASE)
    
    # Pattern 2: Match unquoted src (src=filename followed by space, >, or />
    pattern_unquoted = r'<img[^>]*src=([^\s>]+)'
    matches_unquoted = re.findall(pattern_unquoted, html_content, re.IGNORECASE)
    
    # Combine matches and process
    all_matches = matches_quoted + matches_unquoted
    seen = set()
    
    for match in all_matches:
        # Remove any query parameters or fragments
        filename = match.split('?')[0].split('#')[0].strip()
        # Remove surrounding quotes if present
        filename = filename.strip('"\'')
        # Skip data URIs and empty filenames, and deduplicate
        if filename and not filename.startswith('data:') and filename not in seen:
            images.append(filename)
            seen.add(filename)
    
    return images


def normalize_filename(filename, concept_word=None):
    """
    Normalize and correct a badly named image filename.
    If concept_word is provided, try to create a better filename.
    """
    if not filename:
        return None
    
    # Get file extension
    ext = Path(filename).suffix.lower()
    if not ext:
        ext = '.png'  # Default extension
    
    # If we have a concept word, create a better filename
    if concept_word:
        # Sanitize the word for filename
        safe_word = re.sub(r'[^\w\s-]', '', concept_word.lower())
        safe_word = re.sub(r'[-\s]+', '_', safe_word)
        safe_word = safe_word.strip('_')
        return f"{safe_word}{ext}"
    
    # Otherwise, try to clean up the existing filename
    cleaned = re.sub(r'[^\w\s.-]', '', filename)
    cleaned = re.sub(r'[-\s]+', '_', cleaned)
    return cleaned.strip('_')


def build_english_to_concept_map(graph):
    """
    Build a dictionary mapping English words (from Chinese word definitions) to concept URIs.
    This is used to match English words from Anki cards to concepts.
    
    Strategy:
    1. Find all Word nodes (Chinese words)
    2. Get their English definitions/translations (srs-kg:definition with lang="en")
    3. Extract English words from those definitions
    4. Map English words -> concept URIs via the "means" relationship
    
    Returns a dict: {english_word_lowercase: concept_uri}
    """
    print("  Building English-to-concept mapping from Chinese word definitions...")
    start_time = time.time()
    
    english_to_concept = {}
    
    try:
        # Find all Word instances (Chinese words)
        word_uris = set()
        for word_uri, _, _ in graph.triples((None, RDF.type, SRS_KG.Word)):
            word_uris.add(word_uri)
        
        print(f"    Found {len(word_uris)} Word instances, processing...")
        
        count = 0
        processed = 0
        for word_uri in word_uris:
            processed += 1
            if processed % 1000 == 0:
                elapsed = time.time() - start_time
                print(f"    Progress: {processed}/{len(word_uris)} words processed ({elapsed:.1f}s)...")
            
            # Get the concept URI via "means" relationship
            concept_uri = None
            for _, _, concept in graph.triples((word_uri, SRS_KG.means, None)):
                concept_uri = concept
                break
            
            if not concept_uri:
                continue
            
            # Get English definition/translation from the word
            english_text = None
            
            # Method 1: Direct definition property with lang="en"
            for _, _, definition_obj in graph.triples((word_uri, SRS_KG.definition, None)):
                definition_str = str(definition_obj).strip()
                lang = definition_obj.language if hasattr(definition_obj, 'language') else None
                
                # Check if it's English (lang="en" or no lang and looks like English)
                is_english = (lang == "en" or (lang is None and definition_str and not any(ord(c) > 127 for c in definition_str)))
                
                if is_english and definition_str:
                    english_text = definition_str
                    break
            
            # Method 2: Try concept label if no direct definition
            if not english_text:
                for _, _, label_obj in graph.triples((concept_uri, RDFS.label, None)):
                    label_str = str(label_obj).strip()
                    lang = label_obj.language if hasattr(label_obj, 'language') else None
                    
                    # Check if it's English
                    is_english = (lang == "en" or (lang is None and label_str and not any(ord(c) > 127 for c in label_str)))
                    
                    if is_english and label_str:
                        # Remove "concept:" prefix if present
                        if label_str.startswith("concept:"):
                            label_str = label_str[8:].strip()
                        english_text = label_str
                        break
            
            # Extract English words from the text
            if english_text:
                # Extract individual words (alphanumeric, at least 3 chars)
                words = re.findall(r'\b[a-zA-Z]{3,}\b', english_text.lower())
                
                for word in words:
                    # Store mapping (first concept wins for each word)
                    if word not in english_to_concept:
                        english_to_concept[word] = concept_uri
                        count += 1
        
        elapsed = time.time() - start_time
        print(f"  ✅ Built mapping for {count} English words to {len(set(english_to_concept.values()))} concepts in {elapsed:.2f}s")
        return english_to_concept
    except Exception as e:
        print(f"  ⚠️  Error building English-to-concept map: {e}")
        import traceback
        traceback.print_exc()
        return {}


def find_concept_for_english_word(english_to_concept_map, english_word):
    """
    Find the concept URI for a given English word using the pre-built map.
    
    The map is built from concept labels (rdfs:label), so this matches
    English words from Anki cards to concepts via their English labels.
    
    Returns the concept URI if found, None otherwise.
    
    IMPORTANT: Only does exact matching to avoid incorrect partial matches.
    """
    if not english_word:
        return None
    
    search_word = english_word.lower().strip()
    
    # Only do exact match (O(1) lookup)
    # This matches English words from Anki cards to concepts via concept labels
    if search_word in english_to_concept_map:
        return english_to_concept_map[search_word]
    
    return None


def load_media_map(extract_dir):
    """
    Load Anki's media map file which maps numeric IDs to actual filenames.
    Returns a dict: {numeric_id: actual_filename}
    """
    import json
    
    # Anki stores media map in 'media' file (JSON format)
    media_map_path = os.path.join(extract_dir, 'media')
    if not os.path.exists(media_map_path):
        return {}
    
    try:
        with open(media_map_path, 'r', encoding='utf-8') as f:
            media_map = json.load(f)
        return media_map
    except Exception as e:
        print(f"    ⚠️  Could not load media map: {e}")
        return {}


def copy_image_to_media_dir(image_filename, source_extract_dir, target_media_dir, corrected_filename, media_map=None, reverse_media_map=None):
    """
    Copy an image file from the Anki package to our media directory.
    
    Anki stores media files in the root of extract_dir with NUMERIC NAMES (like "0", "1", "559").
    The HTML references use actual filenames (like "peacock.png").
    The media_map maps: numeric_id -> filename (e.g., "559" -> "peacock.png")
    The reverse_media_map maps: filename -> numeric_id (e.g., "peacock.png" -> "559")
    
    Process:
    1. HTML has <img src="peacock.png">
    2. Look up "peacock.png" in reverse_media_map to get "559"
    3. Find file "559" in extract_dir root
    4. Copy it to target with corrected filename "peacock.png"
    
    Returns the path relative to project root if successful, None otherwise.
    """
    # image_filename from HTML is typically an actual filename (like "peacock.png")
    # We need to find the numeric ID that stores this file
    
    numeric_id = None
    actual_filename = image_filename
    
    # Try to find the numeric ID for this filename
    if reverse_media_map and image_filename in reverse_media_map:
        numeric_id = reverse_media_map[image_filename]
        # Use the actual filename for the target (not the numeric ID)
        if not corrected_filename:
            corrected_filename = image_filename
    elif image_filename.isdigit() and media_map and image_filename in media_map:
        # If image_filename is already a numeric ID, get the actual filename
        numeric_id = image_filename
        actual_filename = media_map[image_filename]
        if not corrected_filename:
            corrected_filename = actual_filename
    
    # Build search paths - files are stored with numeric IDs in root
    search_paths = []
    if numeric_id:
        # Primary: look for the numeric ID file
        search_paths.append(os.path.join(source_extract_dir, numeric_id))
    
    # Fallback: try the filename directly (in case files are stored with actual names)
    search_paths.extend([
        os.path.join(source_extract_dir, image_filename),
        os.path.join(source_extract_dir, actual_filename),
    ])
    
    source_path = None
    for path in search_paths:
        if os.path.exists(path) and os.path.isfile(path):
            source_path = path
            break
    
    if not source_path:
        return None
    
    # Create target directory if it doesn't exist
    os.makedirs(target_media_dir, exist_ok=True)
    
    # Use corrected filename (the actual filename from HTML, not numeric ID)
    target_filename = corrected_filename or actual_filename or image_filename
    target_path = os.path.join(target_media_dir, target_filename)
    
    try:
        shutil.copy2(source_path, target_path)
        # Return relative path from project root
        rel_path = os.path.relpath(target_path, project_root)
        return rel_path
    except Exception as e:
        return None


def get_image_mime_type(filepath):
    """Determine MIME type from file extension."""
    ext = Path(filepath).suffix.lower()
    mime_types = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.svg': 'image/svg+xml',
    }
    return mime_types.get(ext, 'image/png')


def generate_image_uri(image_id):
    """Generate a URI for a visual image instance."""
    return INST[f"image-{image_id}"]


def populate_visual_images(force_reprocess=False):
    """
    Main function to populate visual images from Anki packages.
    
    Args:
        force_reprocess: If True, remove existing VisualImage links and re-process all images.
                        If False, skip images that already exist in the knowledge graph.
    """
    script_start_time = time.time()
    print("=" * 80)
    print("Visual Images Knowledge Graph Populator")
    print("=" * 80)
    print()
    
    # Load existing knowledge graph
    print("Phase 1: Loading knowledge graph...")
    phase_start = time.time()
    graph = Graph()
    graph.bind("srs-kg", SRS_KG)
    graph.bind("srs-inst", INST)
    
    if os.path.exists(KG_FILE):
        print(f"  Loading from: {KG_FILE}")
        try:
            graph.parse(KG_FILE, format="turtle")
            elapsed = time.time() - phase_start
            print(f"  ✅ Loaded existing graph with {len(graph)} triples ({elapsed:.2f}s)")
        except Exception as e:
            print(f"  ⚠️  Warning: Could not parse KG file: {e}")
            print("     Starting with empty graph...")
    else:
        print(f"  ⚠️  Knowledge graph file not found: {KG_FILE}")
        print("     Starting with empty graph...")
    
    print()
    
    # Load ontology schema
    print("Phase 2: Loading ontology schema...")
    phase_start = time.time()
    if os.path.exists(SCHEMA_FILE):
        try:
            graph.parse(SCHEMA_FILE, format="turtle")
            elapsed = time.time() - phase_start
            print(f"  ✅ Ontology schema loaded ({elapsed:.2f}s)")
        except Exception as e:
            print(f"  ⚠️  Warning: Could not parse schema: {e}")
    else:
        print(f"  ⚠️  Schema file not found: {SCHEMA_FILE}")
    print()
    
    # Remove existing VisualImage links if force_reprocess is True
    if force_reprocess:
        print("Phase 3a: Removing existing VisualImage links...")
        phase_start = time.time()
        removed_count = 0
        
        # Find all VisualImage instances
        image_uris = []
        for image_uri, _, _ in graph.triples((None, RDF.type, SRS_KG.VisualImage)):
            image_uris.append(image_uri)
        
        # Remove all triples related to these images
        for image_uri in image_uris:
            # Remove image type
            graph.remove((image_uri, RDF.type, SRS_KG.VisualImage))
            # Remove all properties of the image
            for prop in [SRS_KG.imageFileName, SRS_KG.imageFilePath, SRS_KG.originalFileName,
                        SRS_KG.sourcePackage, SRS_KG.imageMimeType, RDFS.label]:
                graph.remove((image_uri, prop, None))
            # Remove hasVisualization relationships from concepts
            for concept_uri, _, _ in graph.triples((None, SRS_KG.hasVisualization, image_uri)):
                graph.remove((concept_uri, SRS_KG.hasVisualization, image_uri))
            removed_count += 1
        
        elapsed = time.time() - phase_start
        print(f"  ✅ Removed {removed_count} existing VisualImage instances ({elapsed:.2f}s)")
        print()
    
    # Build English-to-concept mapping upfront (much faster than querying per word)
    # This maps English words from Anki cards to concepts via Chinese word definitions
    print("Phase 3: Building English-to-concept mapping from Chinese word definitions...")
    phase_start = time.time()
    english_to_concept_map = build_english_to_concept_map(graph)
    elapsed = time.time() - phase_start
    print(f"  Total time: {elapsed:.2f}s")
    print()
    
    # Process each Anki package
    print("Phase 4: Processing Anki packages...")
    image_count = 0
    concept_link_count = 0
    skipped_count = 0
    
    for pkg_idx, apkg_path in enumerate(ANKI_PACKAGES, 1):
        package_name = os.path.basename(apkg_path)
        print(f"\nPackage {pkg_idx}/{len(ANKI_PACKAGES)}: {package_name}")
        print("-" * 80)
        pkg_start_time = time.time()
        
        # Create temporary extraction directory
        temp_dir = os.path.join(project_root, 'temp_anki_extract', Path(apkg_path).stem)
        os.makedirs(temp_dir, exist_ok=True)
        
        try:
            # Extract the package
            print("  Extracting package...")
            extract_start = time.time()
            extract_dir = extract_apkg(apkg_path, temp_dir)
            if not extract_dir:
                continue
            extract_elapsed = time.time() - extract_start
            print(f"  Extraction time: {extract_elapsed:.2f}s")
            
            # Find the database file. Prefer the new .anki21/.anki21b format (modern Anki versions).
            # Modern Anki exports include both collection.anki21/anki21b (the real database) 
            # and collection.anki2 (a tiny stub file with just a "Please update..." note).
            # The 'b' suffix appears to be used in some Anki versions.
            db_path_v21b = os.path.join(extract_dir, 'collection.anki21b')
            db_path_v21 = os.path.join(extract_dir, 'collection.anki21')
            db_path_v20 = os.path.join(extract_dir, 'collection.anki2')
            
            db_path = None
            if os.path.exists(db_path_v21b):
                db_path = db_path_v21b
                print("  ✅ Found modern .anki21b database")
            elif os.path.exists(db_path_v21):
                db_path = db_path_v21
                print("  ✅ Found modern .anki21 database")
            elif os.path.exists(db_path_v20):
                db_path = db_path_v20
                print("  ⚠️  Found legacy .anki2 database (may be incomplete)")
            else:
                # Try alternative names if not in the root
                for filename in sorted(os.listdir(extract_dir), reverse=True):  # Prefer newer formats
                    if filename.endswith('.anki21b'):
                        db_path = os.path.join(extract_dir, filename)
                        print(f"  ✅ Found modern database: {filename}")
                        break
                    elif filename.endswith('.anki21'):
                        db_path = os.path.join(extract_dir, filename)
                        print(f"  ✅ Found modern database: {filename}")
                        break
                    elif filename.endswith('.anki2') and db_path is None:
                        db_path = os.path.join(extract_dir, filename)
                        print(f"  ⚠️  Found legacy database: {filename}")
            
            if not db_path:
                print(f"  ❌ Could not find database file in {extract_dir}")
                continue
            
            # Read cards from database
            print("  Reading database...")
            db_start = time.time()
            cards = read_anki_database(db_path)
            db_elapsed = time.time() - db_start
            print(f"  Database read time: {db_elapsed:.2f}s")
            
            # Load media map (maps numeric IDs to actual filenames)
            # Note: The 'media' file is the JSON map, not a directory
            print("  Loading media map...")
            media_map = load_media_map(extract_dir)
            reverse_media_map = {}  # filename -> numeric_id
            if media_map:
                print(f"  ✅ Loaded media map with {len(media_map)} entries")
                # Create reverse map (filename -> numeric_id) for lookup
                reverse_media_map = {v: k for k, v in media_map.items()}
                # Show sample entries for debugging
                sample_entries = list(media_map.items())[:3]
                print(f"    Sample: {sample_entries}")
            else:
                print(f"  ⚠️  No media map found (will try direct filename lookup)")
            
            # Media files are stored in the root of extract_dir, not in a subdirectory
            # List actual image files in the extract directory
            extract_files = [f for f in os.listdir(extract_dir) 
                           if os.path.isfile(os.path.join(extract_dir, f)) 
                           and f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'))]
            print(f"  Found {len(extract_files)} image files in extract directory")
            if extract_files:
                print(f"    Sample files: {extract_files[:5]}")
            
            # Process each card
            total_cards = len(cards)
            print(f"  Processing {total_cards} cards...")
            cards_start = time.time()
            
            cards_with_images = 0
            skipped_existing = 0
            for card_idx, card in enumerate(cards):
                # Show progress more frequently
                if (card_idx + 1) % 50 == 0 or (card_idx + 1) == total_cards:
                    elapsed = time.time() - cards_start
                    rate = (card_idx + 1) / elapsed if elapsed > 0 else 0
                    print(f"    Progress: {card_idx + 1}/{total_cards} cards ({rate:.1f} cards/sec, {elapsed:.1f}s elapsed)...")
                
                # Get the front field (where images are typically stored)
                # Check multiple possible field names
                front_content = (
                    card.get('Front') or 
                    card.get('front') or 
                    card.get('Question') or 
                    card.get('question') or
                    card.get('field_0', '')
                )
                
                if not front_content:
                    continue
                
                # Extract image filenames from HTML (Front field only)
                image_filenames = extract_images_from_html(front_content)
                
                # Filter out external URLs (can't download those)
                image_filenames = [img for img in image_filenames if not img.startswith('http')]
                
                if not image_filenames:
                    continue
                
                cards_with_images += 1
                
                # Try to find the English word from the card
                # Check multiple possible field names for the word
                english_word = None
                for field_name in ['Front', 'front', 'English', 'english', 'Word', 'word', 
                                  'Question', 'question', 'Text', 'text', 'Term', 'term']:
                    if field_name in card:
                        text = card[field_name]
                        # Remove HTML tags and image tags to get clean text
                        text = re.sub(r'<img[^>]*>', '', text)
                        text = re.sub(r'<[^>]+>', '', text)
                        # Extract first meaningful word (skip empty strings)
                        words = [w.strip() for w in text.strip().split() if w.strip() and len(w.strip()) > 1]
                        if words:
                            english_word = words[0]
                            break
                
                # Find concept for this word (using pre-built map - much faster!)
                concept_uri = None
                if english_word:
                    concept_uri = find_concept_for_english_word(english_to_concept_map, english_word)
                
                # Process each image
                for img_filename in image_filenames:
                    # Generate unique ID for this image
                    image_id = hashlib.md5(f"{package_name}_{card['note_id']}_{img_filename}".encode()).hexdigest()[:12]
                    image_uri = generate_image_uri(image_id)
                    
                    # Check if this image already exists (unless force_reprocess is True)
                    if not force_reprocess:
                        existing = list(graph.triples((image_uri, RDF.type, SRS_KG.VisualImage)))
                        if existing:
                            skipped_existing += 1
                            continue  # Skip if already added
                    
                    # Normalize filename
                    corrected_filename = normalize_filename(img_filename, english_word)
                    
                    # Copy image to our media directory
                    # Media files are in the root of extract_dir
                    image_path = copy_image_to_media_dir(
                        img_filename,
                        extract_dir,
                        MEDIA_DIR,
                        corrected_filename,
                        media_map,
                        reverse_media_map
                    )
                    
                    if not image_path:
                        skipped_count += 1
                        if skipped_count <= 10:  # Show first few failures for debugging
                            # Show what we tried
                            mapped_name = media_map.get(img_filename, "not in map") if media_map else "no map"
                            print(f"    ⚠️  Could not find image: '{img_filename}' (mapped: {mapped_name})")
                        continue
                    
                    # Create VisualImage instance
                    graph.add((image_uri, RDF.type, SRS_KG.VisualImage))
                    graph.add((image_uri, RDFS.label, Literal(f"Visual: {english_word or 'unknown'}")))
                    graph.add((image_uri, SRS_KG.imageFileName, Literal(corrected_filename or img_filename)))
                    graph.add((image_uri, SRS_KG.imageFilePath, Literal(image_path)))
                    graph.add((image_uri, SRS_KG.originalFileName, Literal(img_filename)))
                    graph.add((image_uri, SRS_KG.sourcePackage, Literal(package_name)))
                    
                    mime_type = get_image_mime_type(image_path)
                    graph.add((image_uri, SRS_KG.imageMimeType, Literal(mime_type)))
                    
                    image_count += 1
                    
                    # Link to concept if found
                    if concept_uri:
                        graph.add((concept_uri, SRS_KG.hasVisualization, image_uri))
                        graph.add((image_uri, SRS_KG.representsConcept, concept_uri))
                        concept_link_count += 1
                        if image_count % 10 == 0:  # Only print every 10th image to reduce noise
                            print(f"    ✅ Image {corrected_filename} linked to concept")
                    # Removed the else print to reduce noise
            
            cards_elapsed = time.time() - cards_start
            pkg_elapsed = time.time() - pkg_start_time
            print(f"  ✅ Package complete: {cards_with_images} cards with images, {image_count} new images added")
            if skipped_existing > 0:
                print(f"  ℹ️  Skipped {skipped_existing} images that already exist in knowledge graph")
            print(f"  Processing time: {cards_elapsed:.2f}s ({total_cards/cards_elapsed:.1f} cards/sec)")
            print(f"  Total package time: {pkg_elapsed:.2f}s")
            
            # Clean up temporary directory
            print("  Cleaning up temporary files...")
            shutil.rmtree(temp_dir, ignore_errors=True)
            
        except Exception as e:
            print(f"  ❌ Error processing package: {e}")
            import traceback
            traceback.print_exc()
            # Clean up on error
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    print()
    print("=" * 80)
    print("Phase 5: Saving knowledge graph...")
    save_start = time.time()
    
    if image_count > 0:
        print(f"  Saving to: {KG_FILE}")
        try:
            graph.serialize(destination=KG_FILE, format="turtle")
            save_elapsed = time.time() - save_start
            print(f"  ✅ Saved knowledge graph with {len(graph)} triples ({save_elapsed:.2f}s)")
        except Exception as e:
            print(f"  ❌ Error saving knowledge graph: {e}")
    else:
        print("  No images to add. Knowledge graph not updated.")
    
    print()
    print("=" * 80)
    print("Summary:")
    print(f"  Images added: {image_count}")
    print(f"  Images linked to concepts: {concept_link_count}")
    print(f"  Images skipped: {skipped_count}")
    total_elapsed = time.time() - script_start_time
    print(f"  Total execution time: {total_elapsed:.2f}s ({total_elapsed/60:.1f} minutes)")
    print("=" * 80)


if __name__ == "__main__":
    import sys
    # Check for --force flag to re-process existing images
    force_reprocess = "--force" in sys.argv or "-f" in sys.argv
    if force_reprocess:
        print("⚠️  FORCE REPROCESS MODE: Will remove all existing VisualImage links and re-process all images")
        print()
    populate_visual_images(force_reprocess=force_reprocess)

