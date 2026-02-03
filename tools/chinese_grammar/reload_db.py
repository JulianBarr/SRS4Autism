import requests
from pathlib import Path

OXIGRAPH_URL = "http://localhost:7878"
UPDATE_ENDPOINT = f"{OXIGRAPH_URL}/update"
STORE_ENDPOINT = f"{OXIGRAPH_URL}/store?default"

FILES = [
    "knowledge_graph/world_model_core.ttl",       # Layer 1: Core
    "tools/chinese_grammar/grammar_layer.ttl"     # Layer 2: Grammar
]

def run():
    # 1. Clear Database
    print("🧹 Clearing Database...")
    requests.post(UPDATE_ENDPOINT, data="DELETE WHERE { ?s ?p ?o }", headers={"Content-Type": "application/sparql-update"})

    # 2. Load Files
    for file_path in FILES:
        path = Path(file_path)
        if not path.exists():
            print(f"❌ Missing: {path}")
            continue
            
        print(f"🚀 Loading {path.name}...")
        with open(path, 'rb') as f:
            requests.post(STORE_ENDPOINT, data=f.read(), headers={"Content-Type": "text/turtle"})
    
    print("✅ Database Reloaded Successfully!")

if __name__ == "__main__":
    run()
