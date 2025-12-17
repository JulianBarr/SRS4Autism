import sys
import zipfile
import sqlite3
import tempfile
import re
from pathlib import Path
from rdflib import Graph, Namespace, Literal, RDF

# Force real-time output
sys.stdout.reconfigure(line_buffering=True)

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent
# We prioritize 'complete' as it has the pinyin/images, but fallback to final if needed
KG_PATH = BASE_DIR / "knowledge_graph" / "world_model_complete.ttl"
if not KG_PATH.exists():
    KG_PATH = BASE_DIR / "knowledge_graph" / "world_model_final.ttl"

DECK_PATH = BASE_DIR / "data" / "content_db" / "English__Vocabulary__2. Level 2.apkg"
SRS_KG = Namespace("http://srs4autism.com/schema/")

def clean_text(text):
    if not text: return ""
    text = re.sub(r'<[^>]+>', '', text) # No HTML
    text = re.sub(r'\[.*?\]', '', text) # No Sound tags
    return text.strip().lower()

def tag_vocabulary():
    print("--- STARTING HIGH-PERFORMANCE TAGGING ---")
    print(f"Target Graph: {KG_PATH.name}")
    
    if not DECK_PATH.exists():
        print(f"❌ Deck not found: {DECK_PATH}")
        return

    # 1. LOAD GRAPH
    print("[1/5] Loading Graph (~45s)...")
    g = Graph()
    g.parse(KG_PATH, format="turtle")
    print(f"      Loaded {len(g)} triples.")

    # 2. BUILD INDEXES (The Speed Secret)
    # We map data into Python dicts so we never have to query the graph in the loop
    print("[2/5] Indexing Graph (Building 'Phone Book')...")
    
    # Map: "apple" -> [URI_Apple_En, URI_Apple_Zh]
    text_to_nodes = {}
    # Map: Concept_URI -> [Word_URI_1, Word_URI_2] (For inheritance)
    concept_to_words = {}
    
    # Iterate ALL words once
    for w_uri in g.subjects(RDF.type, SRS_KG.Word):
        # Index Text
        text_val = g.value(w_uri, SRS_KG.text)
        if text_val:
            clean_t = str(text_val).strip().lower()
            if clean_t not in text_to_nodes:
                text_to_nodes[clean_t] = []
            text_to_nodes[clean_t].append(w_uri)
        
        # Index Concept (for finding synonyms/translations)
        concept_uri = g.value(w_uri, SRS_KG.means)
        if concept_uri:
            if concept_uri not in concept_to_words:
                concept_to_words[concept_uri] = []
            concept_to_words[concept_uri].append(w_uri)

    print(f"      Indexed {len(text_to_nodes)} unique words.")

    # 3. EXTRACT ANKI WORDS
    print("[3/5] Extracting words from Anki Deck...")
    anki_words = set()
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(DECK_PATH, 'r') as z:
            z.extractall(tmpdir)
            db_path = Path(tmpdir) / "collection.anki2"
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT flds FROM notes")
            for row in cursor.fetchall():
                fields = row[0].split('\x1f')
                if len(fields) > 1:
                    clean = clean_text(fields[1]) # Field 1 is Back
                    if clean: anki_words.add(clean)
            conn.close()
    
    target_list = list(anki_words)
    print(f"      Found {len(target_list)} unique words in deck.")

    # 4. TAGGING (Instant Lookup)
    print("[4/5] Applying Tags...")
    triples_to_add = []
    
    for i, word in enumerate(target_list):
        # Progress Report every 100 items
        if i % 100 == 0:
            print(f"      Progress: {i}/{len(target_list)}...", end='\r')
            
        # O(1) Lookup
        matching_nodes = text_to_nodes.get(word, [])
        
        for node in matching_nodes:
            # A. Tag the English Word
            triples_to_add.append((node, SRS_KG.learningTheme, Literal("Logic City")))
            triples_to_add.append((node, SRS_KG.learningLevel, Literal(2)))
            
            # B. Inheritance (Find Chinese/Siblings via Concept Index)
            # We use the index we built, avoiding graph queries
            concept = g.value(node, SRS_KG.means) # This is fast enough for single lookup
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