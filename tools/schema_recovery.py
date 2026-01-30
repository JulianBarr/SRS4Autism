import sys
from collections import defaultdict
from pathlib import Path
from rdflib import Graph, RDF, RDFS, OWL

# CONFIGURATION
# Point this to your cleanest, most complete data file
KG_FILE = Path("knowledge_graph/world_model_rescued.ttl") 
if not KG_FILE.exists():
    # Fallback to complete if rescued doesn't exist in this context
    KG_FILE = Path("knowledge_graph/world_model_complete.ttl")

def analyze_graph():
    print(f"Loading {KG_FILE}...")
    g = Graph()
    g.parse(KG_FILE, format="turtle")
    print(f"Loaded {len(g)} triples.")

    classes = set()
    prop_signatures = defaultdict(int) # (SubjectType, Predicate, ObjectType) -> Count
    
    print("Analyzing structure...")
    
    # 1. Identify all typed instances
    # Map: NodeURI -> ClassURI
    instance_types = {}
    for s, o in g.subject_objects(RDF.type):
        instance_types[s] = o
        classes.add(o)

    # 2. Analyze Predicates
    for s, p, o in g:
        if p == RDF.type: continue
        
        # Determine Subject Type
        sType = instance_types.get(s, "Unknown/Literal")
        
        # Determine Object Type
        oType = "Literal"
        if isinstance(o, type(s)): # If object is a URIRef or BNode
            oType = instance_types.get(o, "ExternalURI")
        
        # Record Signature
        signature = (sType, p, oType)
        prop_signatures[signature] += 1

    # 3. Generate Markdown Report
    print("\n=== GENERATING SCHEMA REPORT ===\n")
    
    print("## 1. Detected Classes")
    for c in sorted(classes):
        print(f"- {c}")
        
    print("\n## 2. Property Usage (Domain -> Predicate -> Range)")
    print("| Subject Class | Predicate | Object Class | Count |")
    print("|---|---|---|---|")
    
    # Sort by Subject Class then Predicate
    sorted_props = sorted(prop_signatures.items(), key=lambda x: (str(x[0][0]), str(x[0][1])))
    
    for (sType, pred, oType), count in sorted_props:
        # Simplify URIs for readability
        s_short = str(sType).split('/')[-1]
        p_short = str(pred).split('/')[-1]
        o_short = str(oType).split('/')[-1]
        
        print(f"| {s_short} | {p_short} | {o_short} | {count} |")

if __name__ == "__main__":
    analyze_graph()
