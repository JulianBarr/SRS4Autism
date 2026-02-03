import pyoxigraph
from pyoxigraph import RdfFormat  # <--- Import this
from pathlib import Path

# ... (Paths remain the same) ...
DB_PATH = Path(__file__).parent.parent.parent / "knowledge_graph"
CORE_TTL = Path(__file__).parent.parent.parent / "knowledge_graph/world_model_core.ttl"
GRAMMAR_TTL = Path(__file__).parent / "grammar_layer.ttl"

def migrate():
    print(f"📂 Targeting Database at: {DB_PATH.resolve()}")
    
    if not DB_PATH.exists():
        print(f"❌ Error: Database folder not found at {DB_PATH}")
        return

    try:
        store = pyoxigraph.Store(str(DB_PATH))
    except OSError as e:
        print(f"❌ Could not open database. Is the backend running? STOP IT FIRST.")
        print(f"   Error: {e}")
        return

    print("🧹 Wiping old 'GrammarPoint' data...")
    delete_query = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    DELETE WHERE {
        ?s a srs-kg:GrammarPoint .
        ?s ?p ?o .
    }
    """
    store.update(delete_query)
    print("   Old grammar data removed.")

    if CORE_TTL.exists():
        print(f"🚀 Reloading Core Schema: {CORE_TTL.name}")
        with open(CORE_TTL, 'rb') as f:
            # FIX: Use RdfFormat.TURTLE instead of string "text/turtle"
            store.load(f, RdfFormat.TURTLE, base_iri="http://srs4autism.com/")
    else:
        print(f"⚠️ Core file not found at {CORE_TTL}. Skipping.")

    if GRAMMAR_TTL.exists():
        print(f"🚀 Loading New Grammar Layer: {GRAMMAR_TTL.name}")
        with open(GRAMMAR_TTL, 'rb') as f:
            # FIX: Use RdfFormat.TURTLE
            store.load(f, RdfFormat.TURTLE, base_iri="http://srs4autism.com/")
        print("✅ Success! New grammar data injected.")
    else:
        print(f"❌ Error: New grammar file missing at {GRAMMAR_TTL}")

if __name__ == "__main__":
    migrate()
