import sys
import shutil
from pathlib import Path
import pyoxigraph
from pyoxigraph import RdfFormat

# Path Setup
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent

# 1. SOURCES (The readable text files)
SOURCE_DIR = PROJECT_ROOT / "knowledge_graph"
# Try to find the core file
if (SOURCE_DIR / "world_model_core.ttl").exists():
    CORE_TTL = SOURCE_DIR / "world_model_core.ttl"
else:
    CORE_TTL = SOURCE_DIR / "world_model_rescued.ttl"

GRAMMAR_TTL = CURRENT_DIR / "grammar_layer.ttl"

# 2. DESTINATION (The binary database in 'data')
DB_PATH = PROJECT_ROOT / "data" / "knowledge_graph_store"

def migrate():
    print(f"📂 Targeting Database at: {DB_PATH}")
    
    if not DB_PATH.exists():
        DB_PATH.mkdir(parents=True, exist_ok=True)

    try:
        # Use the path string for the store
        store = pyoxigraph.Store(str(DB_PATH))
    except OSError:
        print("❌ DB Locked. Is the app running? Please Stop it first!")
        return

    # Clear old data
    print("🧹 Wiping DB for fresh import...")
    store.update("DELETE WHERE { ?s ?p ?o }")

    # Load Source 1: Core
    if CORE_TTL.exists():
        print(f"🚀 Loading Core Schema: {CORE_TTL.name}")
        with open(CORE_TTL, 'rb') as f:
            store.load(f, RdfFormat.TURTLE, base_iri="http://srs4autism.com/")
    else:
        print(f"⚠️ Warning: Could not find a core TTL file in {SOURCE_DIR}")

    # Load Source 2: Grammar
    if GRAMMAR_TTL.exists():
        print(f"🚀 Loading Grammar Layer: {GRAMMAR_TTL.name}")
        with open(GRAMMAR_TTL, 'rb') as f:
            store.load(f, RdfFormat.TURTLE, base_iri="http://srs4autism.com/")
        print("✅ Migration Success!")
    else:
        print(f"❌ Error: {GRAMMAR_TTL.name} missing.")

if __name__ == "__main__":
    migrate()
