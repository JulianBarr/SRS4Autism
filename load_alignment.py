import pyoxigraph
from pathlib import Path

DB_PATH = Path("data/knowledge_graph_store")
file_path = Path("knowledge_graph/ontology/hhs_vbmapp_draft_alignment.ttl")

store = pyoxigraph.Store(str(DB_PATH))
with open(file_path, "rb") as f:
    store.bulk_load(f, pyoxigraph.RdfFormat.TURTLE)

count = sum(1 for _ in store.quads_for_pattern(None, None, None))
print(f"✅ alignment loaded. Total DB triples: {count}")
