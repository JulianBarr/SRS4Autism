from rdflib import Graph
from pathlib import Path

FINAL_FILE = Path(__file__).resolve().parent.parent / "knowledge_graph" / "world_model_final_master.ttl"

print(f"🧐 Formal Audit: {FINAL_FILE.name}")
try:
    g = Graph()
    g.parse(FINAL_FILE, format="turtle")
    print(f"✅ SUCCESS! Total Triples: {len(g)}")
    # Verify a few samples
    q_ids = len(list(g.objects(None, g.namespace_manager.expand_curie("srs-kg:wikidataId"))))
    print(f"📊 Wikidata IDs successfully merged: {q_ids}")
except Exception as e:
    print(f"❌ FAILED: {e}")
