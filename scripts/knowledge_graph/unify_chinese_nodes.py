import sys
import urllib.parse
import re
from pathlib import Path
from rdflib import Graph, Namespace, RDF, URIRef

# Force output
sys.stdout.reconfigure(line_buffering=True)

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent
KG_PATH = BASE_DIR / "knowledge_graph" / "world_model_complete.ttl"
SRS_KG = Namespace("http://srs4autism.com/schema/")

def sanitize_for_uri(text):
    """
    Creates a valid URI suffix from text.
    1. Trims whitespace.
    2. Replaces spaces with underscores.
    3. Removes brackets/parentheses to avoid URI syntax errors.
    4. Keeps Chinese characters readable (does not percent-encode them).
    """
    if not text: return "unknown"
    safe = str(text).strip()
    safe = safe.replace(" ", "_")
    safe = safe.replace("(", "")
    safe = safe.replace(")", "")
    safe = safe.replace("（", "") # Chinese parenthesis
    safe = safe.replace("）", "") # Chinese parenthesis
    return safe

def unify_nodes():
    print("--- STARTING CHINESE NODE UNIFICATION (SAFE MODE) ---")
    print(f"Target Graph: {KG_PATH.name}")

    if not KG_PATH.exists():
        print(f"❌ Graph not found: {KG_PATH}")
        return

    # 1. LOAD GRAPH
    print("[1/4] Loading Graph (this may take a minute)...")
    g = Graph()
    g.parse(KG_PATH, format="turtle")
    print(f"      Loaded {len(g)} triples.")

    # 2. IDENTIFY URL-ENCODED NODES
    print("[2/4] Scanning for URL-encoded nodes...")
    
    candidates = []
    # Find nodes that look like "word-%..." but NOT "word-zh-"
    for s in g.subjects(RDF.type, SRS_KG.Word):
        uri_str = str(s)
        if "%" in uri_str and "word-zh-" not in uri_str:
            candidates.append(s)

    print(f"      Found {len(candidates)} nodes to migrate.")

    # 3. MIGRATE DATA
    print("[3/4] Migrating data to clean URIs...")
    migrated_count = 0
    triples_added = 0
    
    # Pre-calculate list to avoid modifying graph while iterating
    migration_map = [] 

    for dirty_node in candidates:
        # Strategy: Look for srs-kg:text first
        text_val = g.value(dirty_node, SRS_KG.text)
        
        if not text_val:
            # Fallback: Try to decode the URI itself
            try:
                raw_id = str(dirty_node).split("/")[-1]
                if raw_id.startswith("word-"):
                    raw_id = raw_id[5:]
                decoded_text = urllib.parse.unquote(raw_id)
                text_val = decoded_text
            except:
                continue

        # Sanitize the text for the URI (removes spaces/parens)
        clean_suffix = sanitize_for_uri(text_val)
        clean_node = SRS_KG[f"word-zh-{clean_suffix}"]
        
        migration_map.append((dirty_node, clean_node))

    # Execute Migration
    for dirty_node, clean_node in migration_map:
        # A. Move Outgoing Triples
        for p, o in g.predicate_objects(dirty_node):
            g.add((clean_node, p, o))
            g.remove((dirty_node, p, o))
            triples_added += 1

        # B. Move Incoming Triples
        for s, p in g.subject_predicates(dirty_node):
            g.add((s, p, clean_node))
            g.remove((s, p, dirty_node))
            triples_added += 1
        
        # Ensure clean node has type Word
        g.add((clean_node, RDF.type, SRS_KG.Word))
        
        migrated_count += 1
        if migrated_count % 1000 == 0:
            print(f"      Migrated {migrated_count} nodes...", end='\r')

    print(f"\n      Migration Complete.")
    print(f"      Nodes merged: {migrated_count}")

    # 4. SAVE
    print("[4/4] Saving Unified Graph...")
    try:
        g.serialize(destination=KG_PATH, format="turtle")
        print("✅ Done. The graph is now unified and safe.")
    except Exception as e:
        print(f"\n❌ Serialization Error: {e}")
        print("Restoring backup recommended.")

if __name__ == "__main__":
    unify_nodes()
