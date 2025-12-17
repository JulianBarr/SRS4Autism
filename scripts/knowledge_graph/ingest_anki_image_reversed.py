import sys
import zipfile
import json
import sqlite3
import re
import shutil
import urllib.parse
from pathlib import Path
from rdflib import Graph, Namespace, RDF, RDFS, Literal, URIRef

# Force unbuffered output so you see print statements immediately
sys.stdout.reconfigure(line_buffering=True)

# --- CONFIGURATION ---
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent

# UPDATED PATH: Pointing to your actual large file
ANKI_FILE = PROJECT_ROOT / "data" / "content_db" / "English__Vocabulary.apkg"
KG_FILE = PROJECT_ROOT / "knowledge_graph" / "world_model_pinyin_enriched.ttl"
OUTPUT_KG = PROJECT_ROOT / "knowledge_graph" / "world_model_with_images.ttl"

# Destination for images
MEDIA_DEST = PROJECT_ROOT / "content" / "media" / "images"
TEMP_DIR = PROJECT_ROOT / "temp_anki_extract"

def clean_text(text):
    """
    Cleans the Anki Back field to find the pure English word.
    """
    if not text: return ""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Remove brackets/parentheses
    text = re.sub(r'\(.*?\)', '', text)
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'sound:.*?', '', text) # Remove sound tags
    return text.strip().lower() # Lowercase for matching

def ingest_images():
    print(f"--- STARTING OPTIMIZED IMPORT ---")
    print(f"Target: {ANKI_FILE}")
    
    if not ANKI_FILE.exists():
        print(f"❌ Error: Anki file not found at {ANKI_FILE}")
        return

    # 1. Unzip Anki Package
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR)
    TEMP_DIR.mkdir(parents=True)
    
    print("\n[1/5] Extracting .apkg (Media)...")
    with zipfile.ZipFile(ANKI_FILE, 'r') as zf:
        zf.extractall(TEMP_DIR)

    # 2. Read Media Map
    try:
        with open(TEMP_DIR / "media", "r") as f:
            media_map = json.load(f)
        print(f"      Found {len(media_map)} media files.")
    except FileNotFoundError:
        print("❌ Error: No 'media' file found inside .apkg")
        return

    # 3. Load Knowledge Graph
    print("\n[2/5] Loading Knowledge Graph...")
    g = Graph()
    g.parse(KG_FILE, format="turtle")
    SRS_KG = Namespace("http://srs4autism.com/schema/")
    print(f"      Loaded {len(g)} triples.")

    # --- OPTIMIZATION: PRE-INDEXING ---
    print("\n[3/5] Building Concept Index (The Speed Boost)...")
    concept_lookup = {}
    
    # We fetch ALL words and their concepts in one go
    q_all_words = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    SELECT ?label ?concept WHERE {
        ?w a srs-kg:Word ;
           srs-kg:text ?label ;
           srs-kg:means ?concept .
    }
    """
    count = 0
    for row in g.query(q_all_words):
        # normalize to lowercase for matching
        lbl = str(row.label).strip().lower()
        concept_lookup[lbl] = row.concept
        count += 1
    
    print(f"      Indexed {len(concept_lookup)} unique words from KG.")

    # 4. Read Anki Database
    print("\n[4/5] Processing Anki Database...")
    db_path = TEMP_DIR / "collection.anki21"
    if not db_path.exists():
        db_path = TEMP_DIR / "collection.anki2"
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT flds FROM notes")
    notes = cursor.fetchall()
    
    matches = 0
    images_added = 0
    MEDIA_DEST.mkdir(parents=True, exist_ok=True)

    print(f"      Scanning {len(notes)} cards for images...")
    
    for i, note in enumerate(notes):
        # Progress Bar
        if i % 100 == 0:
            print(f"      Progress: {i}/{len(notes)} (Matches: {matches})", end='\r')

        fields = note[0].split('\x1f')
        if len(fields) < 2: continue
            
        raw_front = fields[0] # Image location
        raw_back = fields[1]  # "Apple"
        
        # 1. Clean English Word
        english_word = clean_text(raw_back)
        if not english_word: continue

        # 2. Check Index (Instant Lookup)
        if english_word in concept_lookup:
            target_concept = concept_lookup[english_word]
            
            # 3. Find Images in Front
            img_refs = re.findall(r'src="([^"]+)"', raw_front)
            
            if img_refs:
                matches += 1
                for filename in img_refs:
                    # Find mapped file
                    media_id = None
                    for k, v in media_map.items():
                        if v == filename:
                            media_id = k
                            break
                    
                    if media_id:
                        src_file = TEMP_DIR / media_id
                        safe_filename = urllib.parse.unquote(filename)
                        
                        if src_file.exists():
                            shutil.copy(src_file, MEDIA_DEST / safe_filename)
                            
                            # Add to Graph
                            img_node_uri = SRS_KG[f"img-{urllib.parse.quote(safe_filename)}"]
                            rel_path = f"content/media/images/{safe_filename}"
                            
                            g.add((img_node_uri, RDF.type, SRS_KG.VisualImage))
                            g.add((img_node_uri, SRS_KG.imageFileName, Literal(safe_filename)))
                            g.add((img_node_uri, SRS_KG.imageFilePath, Literal(rel_path)))
                            
                            # Link
                            g.add((target_concept, SRS_KG.hasVisualization, img_node_uri))
                            g.add((img_node_uri, SRS_KG.representsConcept, target_concept))
                            images_added += 1

    conn.close()
    if TEMP_DIR.exists(): shutil.rmtree(TEMP_DIR)

    print(f"\n\n[5/5] Saving Updated KG...")
    g.serialize(destination=OUTPUT_KG, format="turtle")
    
    print(f"--- COMPLETE ---")
    print(f"Matches found: {matches}")
    print(f"Images linked: {images_added}")
    print(f"Saved to: {OUTPUT_KG}")

if __name__ == "__main__":
    ingest_images()