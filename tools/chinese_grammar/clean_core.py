from rdflib import Graph, Namespace, RDF

# Paths
OLD_TTL = "knowledge_graph/world_model_rescued.ttl"
NEW_CORE_TTL = "knowledge_graph/world_model_core.ttl"

def clean_core():
    print(f"📖 Parsing {OLD_TTL}...")
    g = Graph()
    g.parse(OLD_TTL, format="turtle")
    
    SRS_KG = Namespace("http://srs4autism.com/schema/")
    
    # Find all GrammarPoints
    subjects = list(g.subjects(RDF.type, SRS_KG.GrammarPoint))
    print(f"🧐 Found {len(subjects)} old grammar points.")
    
    # Remove them
    count = 0
    for s in subjects:
        for p, o in g.predicate_objects(s):
            g.remove((s, p, o))
            count += 1
            
    print(f"🧹 Removed {count} triples.")
    g.serialize(destination=NEW_CORE_TTL, format="turtle")
    print(f"✅ Saved clean core to: {NEW_CORE_TTL}")

if __name__ == "__main__":
    clean_core()
