import sys
from pathlib import Path
from pyoxigraph import Store

# --- CONFIG ---
# Resolve paths relative to this script
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "data" / "knowledge_graph_store"
TTL_PATH = BASE_DIR / "tools" / "english_grammar" / "english_grammar_layer.ttl"

def migrate_english():
    print(f"🇬🇧 Starting English Layer Migration...")
    
    if not DB_PATH.exists():
        print(f"❌ Database not found at {DB_PATH}")
        print("   Please run the main setup first (tools/chinese_grammar/migrate_final.py)")
        return

    if not TTL_PATH.exists():
        print(f"❌ TTL file not found: {TTL_PATH}")
        return

    # 1. Open Existing Store (Do NOT wipe it)
    print(f"📂 Opening existing Knowledge Graph at: {DB_PATH.name}")
    try:
        store = Store(str(DB_PATH))
    except OSError as e:
        print(f"❌ Could not lock database: {e}")
        print("   👉 STOP THE RUNNING APP first! (Ctrl+C)")
        return

    # 2. Load English Data
    print(f"📥 Loading English Grammar Layer: {TTL_PATH.name}...")
    try:
        initial_count = sum(1 for _ in store)
        
        with open(TTL_PATH, "rb") as f:
            store.load(f, "text/turtle")
            
        final_count = sum(1 for _ in store)
        added = final_count - initial_count
        
        print(f"   ✅ Success! Added {added} new triples.")
        print(f"   📊 Total Graph Size: {final_count} triples.")
        
    except Exception as e:
        print(f"   ❌ Failed to load: {e}")

if __name__ == "__main__":
    migrate_english()
