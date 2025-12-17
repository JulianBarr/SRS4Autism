import sys
import zipfile
import sqlite3
import tempfile
import re
import html
from pathlib import Path
from rdflib import Graph, Namespace, Literal, RDF

# Force real-time output
sys.stdout.reconfigure(line_buffering=True)

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent
# We prioritize 'complete'
KG_PATH = BASE_DIR / "knowledge_graph" / "world_model_complete.ttl"
if not KG_PATH.exists():
    KG_PATH = BASE_DIR / "knowledge_graph" / "world_model_final.ttl"

DECK_PATH = BASE_DIR / "data" / "content_db" / "English__Vocabulary__2. Level 2.apkg"
SRS_KG = Namespace("http://srs4autism.com/schema/")

def clean_anki_field(text):
    """
    Aggressively cleans Anki HTML to get the raw word.
    Example: '<div>Virtue</div>&nbsp;' -> 'virtue'
    """
    if not text: return ""
    text = html.unescape(text) # &nbsp; -> space
    text = re.sub(r'<[^>]+>', '', text) # Remove tags
    text = re.sub(r'\[.*?\]', '', text) # Remove sound
    text = text.replace(u'\xa0', u' ')
    return text.strip().lower()

def tag_vocabulary():
    print("--- STARTING PRECISION TAGGING ---")
    print(f"Target Graph: {KG_PATH.name}")
    
    if not DECK_PATH.exists():
        print(f"❌ Deck not found: {DECK_PATH}")
        return

    # 1. LOAD GRAPH
    print("[1/5] Loading Graph (~45s)...")
    g = Graph()
    g.parse(KG_PATH, format="turtle")
    print(f"      Loaded {len(g)} triples.")

    # 2. BUILD INDEXES
    print("[2/5] Indexing Graph Words...")
    text_to_nodes = {}
    concept_to_words = {}
    
    for w_uri in g.subjects(RDF.type, SRS_KG.Word):
        text_val = g.value(w_uri, SRS_KG.text)
        if text_val:
            clean_t = str(text_val).strip().lower()
            if clean_t not in text_to_nodes:
                text_to_nodes[clean_t] = []
            text_to_nodes[clean_t].append(w_uri)
        
        concept_uri = g.value(w_uri, SRS_KG.means)
        if concept_uri:
            if concept_uri not in concept_to_words:
                concept_to_words[concept_uri] = []
            concept_to_words[concept_uri].append(w_uri)

    print(f"      Indexed {len(text_to_nodes)} unique words.")

    # 3. EXTRACT ANKI WORDS
    print("[3/5] Extracting words from Deck...")
    anki_words = set()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(DECK_PATH, 'r') as z:
            z.extractall(tmpdir)
            
            # CRITICAL FIX: Prioritize .anki21 (New Format) over .anki2 (Legacy Stub)
            db_path = Path(tmpdir) / "collection.anki21"
            if not db_path.exists():
                db_path = Path(tmpdir) / "collection.anki2"
                
            print(f"      Using Database: {db_path.name}")

            if db_path.exists():
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT flds FROM notes")
                
                rows = cursor.fetchall()
                print(f"      Scanning {len(rows)} notes...") # Debug info
                
                for i, row in enumerate(rows):
                    fields = row[0].split('\x1f')
                    
                    # Debug first row just to be sure
                    if i == 0:
                        print(f"      [DEBUG] First Note Fields: {fields}")

                    # Check Field 1 (Back)
                    if len(fields) > 1:
                        raw = fields[1]
                        clean = clean_anki_field(raw)
                        
                        # Only add if it matches a known graph word
                        if clean and clean in text_to_nodes:
                            anki_words.add(clean)
                conn.close()
            else:
                print("❌ No Anki database found inside .apkg")

    target_list = list(anki_words)
    print(f"      Found {len(target_list)} valid matching words.")

    if len(target_list) == 0:
        print("❌ Still found 0 words. Check the [DEBUG] line above.")
        return

    # 4. TAGGING
    print("[4/5] Applying Tags...")
    triples_to_add = []
    
    for i, word in enumerate(target_list):
        if i % 100 == 0:
            print(f"      Progress: {i}/{len(target_list)}...", end='\r')
            
        matching_nodes = text_to_nodes.get(word, [])
        
        for node in matching_nodes:
            # Tag the Word
            triples_to_add.append((node, SRS_KG.learningTheme, Literal("Logic City")))
            triples_to_add.append((node, SRS_KG.learningLevel, Literal(2)))
            
            # Inheritance (Tag Chinese Synonyms)
            concept = g.value(node, SRS_KG.means)
            if concept and concept in concept_to_words:
                siblings = concept_to_words[concept]
                for sibling in siblings:
                    if sibling != node:
                        triples_to_add.append((sibling, SRS_KG.learningTheme, Literal("Logic City")))
                        triples_to_add.append((sibling, SRS_KG.learningLevel, Literal(2)))

    print(f"\n      Generated {len(triples_to_add)} new tags.")

    # 5. SAVE
    print("[5/5] Saving Graph...")
    for t in triples_to_add:
        g.add(t)
        
    g.serialize(destination=KG_PATH, format="turtle")
    print("✅ Done.")

if __name__ == "__main__":
    tag_vocabulary()