import sys
import re
import os
from pathlib import Path

# --- 1. FORCE OUTPUT (Fixes Silent Death) ---
sys.stdout.reconfigure(line_buffering=True)

try:
    from rdflib import Graph, Namespace, RDF, RDFS, Literal
except ImportError:
    print("❌ Error: rdflib is not installed. Run: pip install rdflib")
    sys.exit(1)

# --- CONFIGURATION ---
# We use the location of *this script* to find the root
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent # scripts -> knowledge_graph -> ROOT

INPUT_FILE = PROJECT_ROOT / "knowledge_graph" / "world_model_merged.ttl"
OUTPUT_FILE = PROJECT_ROOT / "knowledge_graph" / "world_model_bridged.ttl"
CEDICT_FILE = PROJECT_ROOT / "knowledge_graph" / "data" / "cedict_ts.u8"

def parse_cedict(file_path):
    print(f"  -> Reading dictionary from: {file_path}")
    if not file_path.exists():
        print(f"❌ CRITICAL ERROR: Dictionary file not found at {file_path}")
        print("   Please download cedict_ts.u8 and place it in knowledge_graph/data/")
        sys.exit(1)

    dictionary = {}
    count = 0
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('#') or line.strip() == '':
                continue
            # Regex: Traditional Simplified [pin1 yin1] /def1/def2/
            match = re.match(r'(\S+)\s+(\S+)\s+\[.*?\]\s+/(.*)/', line)
            if match:
                simp = match.group(2)
                defs = match.group(3).split('/')
                
                clean_defs = []
                for d in defs:
                    # Remove parentheticals: "friend (archaic)" -> "friend"
                    d_clean = re.sub(r'\(.*?\)', '', d).strip().lower()
                    if d_clean:
                        clean_defs.append(d_clean)
                
                if simp not in dictionary:
                    dictionary[simp] = []
                dictionary[simp].extend(clean_defs)
                count += 1
    
    print(f"  -> Dictionary loaded: {count} entries.")
    return dictionary

def run_bridge():
    print(f"Script started from: {SCRIPT_DIR}")
    print(f"Project Root: {PROJECT_ROOT}")
    
    if not INPUT_FILE.exists():
        print(f"❌ CRITICAL: Input file not found: {INPUT_FILE}")
        return

    # 1. Load Data
    print(f"\n[1/5] Loading Graph {INPUT_FILE.name}...")
    g = Graph()
    g.parse(INPUT_FILE, format="turtle")
    SRS_KG = Namespace("http://srs4autism.com/schema/")
    print(f"      Loaded {len(g)} triples.")

    # 2. Load Dictionary
    print("\n[2/5] Parsing CC-CEDICT...")
    cedict = parse_cedict(CEDICT_FILE)

    # 3. Index English Concepts
    print("\n[3/5] Indexing English target concepts...")
    eng_index = {}
    q_eng = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    SELECT ?wordLabel ?concept WHERE {
        ?w a srs-kg:Word ;
           srs-kg:text ?wordLabel ;
           srs-kg:means ?concept .
        FILTER (lang(?wordLabel) = "en" || REGEX(STR(?w), "word-en-"))
    }
    """
    for row in g.query(q_eng):
        label = str(row.wordLabel).lower().strip()
        eng_index[label] = row.concept
    
    print(f"      Indexed {len(eng_index)} English targets.")
    if len(eng_index) == 0:
        print("⚠️  WARNING: No English concepts found. Bridging will be impossible.")

    # 4. The Bridging Loop
    print("\n[4/5] Bridging Concepts...")
    stats = {"bridged": 0, "failed": 0, "skipped": 0}
    
    q_zh = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    SELECT ?w ?label ?old_concept WHERE {
        ?w a srs-kg:Word ;
           srs-kg:text ?label ;
           srs-kg:means ?old_concept .
        FILTER (lang(?label) = "zh" || REGEX(STR(?w), "word-")) 
        FILTER (!REGEX(STR(?w), "word-en-"))
    }
    """
    
    triples_to_add = []
    triples_to_remove = []
    
    # Progress bar counter
    processed_count = 0
    
    for row in g.query(q_zh):
        processed_count += 1
        if processed_count % 1000 == 0:
            print(f"      Processed {processed_count} words...", end='\r')

        word_uri = row.w
        label = str(row.label)
        old_concept = row.old_concept
        
        if label in cedict:
            translations = cedict[label]
            found_match = False
            
            for trans in translations:
                if trans in eng_index:
                    new_concept = eng_index[trans]
                    
                    if new_concept == old_concept:
                        continue

                    # REWIRE
                    triples_to_remove.append((word_uri, SRS_KG.means, old_concept))
                    triples_to_add.append((word_uri, SRS_KG.means, new_concept))
                    triples_to_add.append((new_concept, SRS_KG.isExpressedBy, word_uri))

                    # ENRICH (Move comments)
                    for comment in g.objects(old_concept, RDFS.comment):
                        triples_to_add.append((new_concept, RDFS.comment, comment))
                    
                    stats["bridged"] += 1
                    found_match = True
                    break 
            
            if not found_match:
                stats["failed"] += 1
        else:
            stats["skipped"] += 1

    print(f"\n      Finished processing {processed_count} words.")

    # 5. Apply Changes
    print(f"\n[5/5] Applying changes (-{len(triples_to_remove)} / +{len(triples_to_add)} triples)...")
    for t in triples_to_remove:
        g.remove(t)
    for t in triples_to_add:
        g.add(t)

    print(f"      Saving to {OUTPUT_FILE.name}...")
    g.serialize(destination=OUTPUT_FILE, format="turtle")
    
    print("\n--- SUMMARY ---")
    print(f"Successfully Bridged: {stats['bridged']} words")
    print(f"No English Match:     {stats['failed']} words")
    print(f"Not in Dictionary:    {stats['skipped']} words")
    print(f"Output saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    run_bridge()