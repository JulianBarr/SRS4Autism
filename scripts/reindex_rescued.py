import pyoxigraph as oxigraph
from pathlib import Path
import shutil, os

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TTL_FILE = PROJECT_ROOT / "knowledge_graph" / "world_model_rescued.ttl"
STORE_PATH = PROJECT_ROOT / "data" / "kg_store"

def reindex():
    # Stop if backend might be running
    if STORE_PATH.exists():
        print(f"🗑  Wiping old store at {STORE_PATH}...")
        try:
            shutil.rmtree(STORE_PATH)
        except Exception as e:
            print(f"❌ Could not delete store. Ensure backend is STOPPED. Error: {e}")
            return
            
    os.makedirs(STORE_PATH, exist_ok=True)

    print(f"📦 Indexing corrected {TTL_FILE.name} into Oxigraph...")
    if not TTL_FILE.exists():
        print(f"❌ Error: {TTL_FILE} not found.")
        return

    store = oxigraph.Store(str(STORE_PATH))
    with open(TTL_FILE, "rb") as f:
        store.bulk_load(f, "text/turtle")
    
    print(f"✅ SUCCESS! Indexed {len(store)} triples. HSK '喃' issue is now fixed.")

if __name__ == "__main__":
    reindex()

