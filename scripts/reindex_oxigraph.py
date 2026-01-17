import pyoxigraph as oxigraph
from pathlib import Path
import shutil
import os

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TTL_FILE = PROJECT_ROOT / "knowledge_graph" / "world_model_final_master.ttl"
STORE_PATH = PROJECT_ROOT / "data" / "kg_store"

def reindex():
    if not TTL_FILE.exists():
        print(f"❌ Error: {TTL_FILE} not found!")
        return

    # 1. Clear existing store to prevent duplicate indexing
    if STORE_PATH.exists():
        print(f"🗑  Removing old store at {STORE_PATH}...")
        shutil.rmtree(STORE_PATH)
    
    os.makedirs(STORE_PATH, exist_ok=True)

    # 2. Open Oxigraph Store
    print(f"📦 Opening Oxigraph Store at {STORE_PATH}...")
    store = oxigraph.Store(str(STORE_PATH))

    # 3. Load Turtle File
    print(f"📖 Parsing {TTL_FILE.name} (this may take a minute)...")
    try:
        with open(TTL_FILE, "rb") as f:
            store.bulk_load(f, "text/turtle")
        
        print(f"✅ SUCCESS! Indexed {len(store)} triples.")
    except Exception as e:
        print(f"❌ Failed to parse TTL: {e}")

if __name__ == "__main__":
    reindex()

