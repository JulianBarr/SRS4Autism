import pyoxigraph as oxigraph
from pathlib import Path
import shutil
import os
import sys

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Files to load (order matters if one depends on another, though RDF is generally order-independent for loading)
DEFAULT_FILES = [
    PROJECT_ROOT / "knowledge_graph" / "world_model_rescued_v3.ttl",
    PROJECT_ROOT / "knowledge_graph" / "world_model_complete_v2.ttl"
]
STORE_PATH = PROJECT_ROOT / "data" / "kg_store"

def reindex(files_to_load=None):
    if files_to_load is None:
        files_to_load = DEFAULT_FILES

    # Verify all files exist
    for ttl_file in files_to_load:
        if not ttl_file.exists():
            print(f"❌ Error: {ttl_file} not found!")
            return

    # 1. Clear existing store to prevent duplicate indexing
    if STORE_PATH.exists():
        print(f"🗑  Removing old store at {STORE_PATH}...")
        shutil.rmtree(STORE_PATH)
    
    os.makedirs(STORE_PATH, exist_ok=True)

    # 2. Open Oxigraph Store
    print(f"📦 Opening Oxigraph Store at {STORE_PATH}...")
    store = oxigraph.Store(str(STORE_PATH))

    # 3. Load Turtle Files
    total_triples = 0
    for ttl_file in files_to_load:
        print(f"📖 Parsing {ttl_file.name}...")
        try:
            # Get count before
            count_before = len(store)
            with open(ttl_file, "rb") as f:
                store.bulk_load(f, "text/turtle")
            count_after = len(store)
            loaded = count_after - count_before
            print(f"   -> Added {loaded} triples.")
        except Exception as e:
            print(f"❌ Failed to parse {ttl_file.name}: {e}")
            return

    final_count = len(store)
    print(f"✅ SUCCESS! Total store size: {final_count} triples.")

if __name__ == "__main__":
    reindex()
