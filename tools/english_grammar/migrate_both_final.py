import shutil
from pathlib import Path
from pyoxigraph import Store

# --- CONFIG ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "data" / "knowledge_graph_store"

# LIST OF ALL LAYERS TO LOAD
FILES_TO_LOAD = [
    # 1. The Ontology (Schema)
    BASE_DIR / "knowledge_graph" / "world_model_core.ttl",
    
    # 2. Chinese Grammar (A1-B2)
    BASE_DIR / "tools" / "chinese_grammar" / "grammar_layer.ttl",
    
    # 3. English Grammar (CEFR-J) - The new layer!
    BASE_DIR / "tools" / "english_grammar" / "english_grammar_layer.ttl"
]

def migrate():
    print("🚀 Starting MASTER Migration (Chinese + English)...")
    
    # 1. Clean Slate (Remove old DB to fix sorting/duplicates)
    if DB_PATH.exists():
        print(f"🗑️  Wiping existing database at {DB_PATH.name}...")
        try:
            shutil.rmtree(DB_PATH)
        except OSError as e:
            print(f"   ❌ Error removing DB: {e}")
            print("   (Make sure the App is STOPPED!)")
            return

    # 2. Create New Store
    print(f"🆕 Creating new store at {DB_PATH}...")
    store = Store(str(DB_PATH))

    # 3. Load All Layers
    for file_path in FILES_TO_LOAD:
        if not file_path.exists():
            print(f"   ⚠️  Skipping missing file: {file_path}")
            continue
            
        print(f"   📥 Loading: {file_path.name}")
        try:
            with open(file_path, "rb") as f:
                store.load(f, "text/turtle")
            print(f"      ✅ Success.")
        except Exception as e:
            print(f"      ❌ Failed to load {file_path.name}: {e}")

    # 4. Verify
    count = sum(1 for _ in store)
    print("-" * 40)
    print(f"🎉 Migration Complete!")
    print(f"📊 Total Triples in Graph: {count}")
    print("-" * 40)

if __name__ == "__main__":
    migrate()
