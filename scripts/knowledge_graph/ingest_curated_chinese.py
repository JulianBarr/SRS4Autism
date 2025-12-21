import sys
import csv
import urllib.parse
from pathlib import Path
from rdflib import Graph, Namespace, Literal, RDF, URIRef

# Force real-time output
sys.stdout.reconfigure(line_buffering=True)

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CSV_PATH = BASE_DIR / "logs" / "vision_cleanup_report.csv"

# We prefer the 'complete' file if it exists (has images/pinyin), otherwise fall back
KG_PATH = BASE_DIR / "knowledge_graph" / "world_model_complete.ttl"
if not KG_PATH.exists():
    KG_PATH = BASE_DIR / "knowledge_graph" / "world_model_chinese_enriched.ttl"

# Output (Save over the input or a new file)
OUTPUT_KG = BASE_DIR / "knowledge_graph" / "world_model_complete.ttl"

SRS_KG = Namespace("http://srs4autism.com/schema/")

def ingest_chinese():
    print("--- CHINESE INGESTION & INHERITANCE SCRIPT ---")
    
    if not CSV_PATH.exists():
        print(f"❌ CSV not found: {CSV_PATH}")
        return

    # 1. LOAD GRAPH
    print(f"[1/4] Loading Graph from {KG_PATH.name} (~45s)...")
    g = Graph()
    g.parse(KG_PATH, format="turtle")
    print(f"      Loaded {len(g)} triples.")

    # 2. BUILD INDEXES (Optimization)
    print("[2/4] Indexing Graph Words...")
    
    # Map: "apple" -> URI_Node
    english_map = {}
    
    for w in g.subjects(RDF.type, SRS_KG.Word):
        # We only care about English words to serve as anchors
        text_val = g.value(w, SRS_KG.text)
        if text_val:
            clean_text = str(text_val).strip().lower()
            english_map[clean_text] = w

    print(f"      Indexed {len(english_map)} English anchors.")

    # 3. PROCESS CSV
    print("[3/4] Processing CSV...")
    
    new_triples = []
    processed_count = 0
    
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            # Skip deletions
            if row['New_Filename'] == "DELETE":
                continue
                
            chinese_text = row.get('Chinese', '').strip()
            english_word = row['English_Word'].strip().lower()
            
            if not chinese_text or not english_word:
                continue

            # A. Find Parent English Node
            english_node = english_map.get(english_word)
            
            if english_node:
                # B. Create Chinese Node URI (UTF-8, No Encoding)
                # Remove spaces just in case
                safe_zh = chinese_text.replace(" ", "")
                zh_uri = SRS_KG[f"word-zh-{safe_zh}"]
                
                # C. Basic Definition
                new_triples.append((zh_uri, RDF.type, SRS_KG.Word))
                new_triples.append((zh_uri, SRS_KG.text, Literal(chinese_text, lang="zh")))
                new_triples.append((zh_uri, SRS_KG.learningLanguage, Literal("zh")))
                
                # D. Link to Meaning (Concept)
                # Get concept from English node
                concept = g.value(english_node, SRS_KG.means)
                if concept:
                    new_triples.append((zh_uri, SRS_KG.means, concept))
                    new_triples.append((concept, SRS_KG.isExpressedBy, zh_uri))
                
                # E. INHERITANCE (The Critical Part)
                # Copy tags from English Parent to Chinese Child
                
                # Level
                level = g.value(english_node, SRS_KG.learningLevel)
                if level:
                    new_triples.append((zh_uri, SRS_KG.learningLevel, level))
                    
                # Theme (Logic City)
                theme = g.value(english_node, SRS_KG.learningTheme)
                if theme:
                    new_triples.append((zh_uri, SRS_KG.learningTheme, theme))
            
            processed_count += 1

    print(f"      Processed {processed_count} CSV rows.")
    print(f"      Generated {len(new_triples)} new/update triples.")

    # 4. SAVE
    print(f"[4/4] Saving to {OUTPUT_KG.name}...")
    for t in new_triples:
        g.add(t)
        
    g.serialize(destination=OUTPUT_KG, format="turtle")
    print("✅ Done.")

if __name__ == "__main__":
    ingest_chinese()