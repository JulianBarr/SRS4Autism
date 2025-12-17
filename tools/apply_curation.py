import sys
import csv
import shutil
import os
import urllib.parse
from pathlib import Path
from rdflib import Graph, Namespace, Literal, RDF, URIRef

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = BASE_DIR / "logs" / "vision_cleanup_report.csv"
MEDIA_DIR = BASE_DIR / "content" / "media" / "images"
KG_PATH = BASE_DIR / "knowledge_graph" / "world_model_with_images.ttl"
OUTPUT_KG = BASE_DIR / "knowledge_graph" / "world_model_chinese_enriched.ttl"

SRS_KG = Namespace("http://srs4autism.com/schema/")

def apply_changes():
    if not CSV_PATH.exists():
        print("❌ Report CSV not found.")
        return

    print("--- STARTING OPTIMIZED APPLY ---")
    
    # 1. LOAD GRAPH
    print("[1/4] Loading Knowledge Graph (this takes ~30s)...")
    g = Graph()
    g.parse(KG_PATH, format="turtle")
    print(f"      Loaded {len(g)} triples.")

    # 2. BUILD INDEXES (The Speed Boost)
    print("[2/4] Building Lookup Indexes...")
    
    # Index A: Filename -> Image Node URI
    # We iterate triples directly (Fast) instead of SPARQL (Slow)
    file_to_uri = {}
    for s, p, o in g.triples((None, SRS_KG.imageFileName, None)):
        file_to_uri[str(o)] = s
    
    print(f"      Indexed {len(file_to_uri)} images.")

    # Index B: English Word Text -> Concept Node URI
    # We need to find the concept for a given English word to add Chinese
    word_to_concept = {}
    
    # Find all Words
    for word_node, _, _ in g.triples((None, RDF.type, SRS_KG.Word)):
        # Get text
        text = g.value(word_node, SRS_KG.text)
        if text:
            # Get concept
            concept = g.value(word_node, SRS_KG.means)
            if concept:
                word_to_concept[str(text).lower().strip()] = concept

    print(f"      Indexed {len(word_to_concept)} concepts.")

    # 3. PROCESS CSV
    print("[3/4] Processing Cleanup Report...")
    
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        count = 0
        renamed = 0
        deleted = 0
        chinese_added = 0
        
        for row in reader:
            count += 1
            if count % 500 == 0:
                print(f"      Processed {count} rows...", end='\r')

            old_name = row['Old_Filename']
            new_name = row['New_Filename']
            chinese_text = row.get('Chinese', '').strip()
            english_word = row['English_Word'].strip()
            
            # --- ACTION 1: DELETE ---
            if new_name == "DELETE":
                # Disk
                file_path = MEDIA_DIR / old_name
                if file_path.exists():
                    os.remove(file_path)
                
                # Graph
                img_uri = file_to_uri.get(old_name)
                if img_uri:
                    # Remove all triples touching this node
                    g.remove((img_uri, None, None))
                    g.remove((None, None, img_uri))
                    del file_to_uri[old_name] # Update index
                
                deleted += 1
                continue

            # --- ACTION 2: RENAME ---
            if old_name != new_name and new_name:
                # Disk
                old_path = MEDIA_DIR / old_name
                new_path = MEDIA_DIR / new_name
                if old_path.exists():
                    shutil.move(old_path, new_path)
                    renamed += 1
                
                # Graph
                img_uri = file_to_uri.get(old_name)
                if img_uri:
                    # Update properties
                    g.set((img_uri, SRS_KG.imageFileName, Literal(new_name)))
                    g.set((img_uri, SRS_KG.imageFilePath, Literal(f"content/media/images/{new_name}")))
                    # Update Index for future lookups (if needed)
                    file_to_uri[new_name] = img_uri 
                    # del file_to_uri[old_name] # Optional cleanup

            # --- ACTION 3: CHINESE VOCAB ---
            if chinese_text:
                # Instant Lookup
                concept_node = word_to_concept.get(english_word.lower())
                
                if concept_node:
                    # Create URI (UTF-8, No URL Encoding)
                    # We strip spaces just in case
                    safe_zh_suffix = chinese_text.replace(" ", "")
                    zh_uri = SRS_KG[f"word-zh-{safe_zh_suffix}"]
                    
                    # Add Triples
                    g.add((zh_uri, RDF.type, SRS_KG.Word))
                    g.add((zh_uri, SRS_KG.text, Literal(chinese_text, lang="zh")))
                    g.add((zh_uri, SRS_KG.learningLanguage, Literal("zh")))
                    
                    # Link to Meaning
                    g.add((zh_uri, SRS_KG.means, concept_node))
                    g.add((concept_node, SRS_KG.isExpressedBy, zh_uri))
                    
                    chinese_added += 1

    print(f"\n\n--- SUMMARY ---")
    print(f"Total Rows:      {count}")
    print(f"Files Renamed:   {renamed}")
    print(f"Files Deleted:   {deleted}")
    print(f"Chinese Words:   {chinese_added}")
    
    # 4. SAVE
    print(f"[4/4] Saving to {OUTPUT_KG}...")
    g.serialize(destination=OUTPUT_KG, format="turtle")
    print("✅ Done.")

if __name__ == "__main__":
    apply_changes()