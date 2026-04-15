import json
import os
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS

def main():
    INPUT_JSON = "vbmapp_level1_normalized.json"
    OUTPUT_TTL = "vbmapp_ontology.ttl"

    print(f"🚀 Loading normalized JSON from {INPUT_JSON}...")
    
    if not os.path.exists(INPUT_JSON):
        print(f"❌ Error: {INPUT_JSON} not found!")
        return

    with open(INPUT_JSON, 'r', encoding='utf-8') as f:
        vbmapp_data = json.load(f)

    # 1. Initialize Graph and Namespaces
    g = Graph()
    ECTA_KG = Namespace("http://ecta.ai/schema/")
    VBMAPP_INST = Namespace("http://ecta.ai/vbmapp/instance/")
    
    g.bind("ecta-kg", ECTA_KG)
    g.bind("vbmapp-inst", VBMAPP_INST)
    g.bind("rdfs", RDFS)

    # Helper function to ensure URIs are valid (e.g., replace hyphens with underscores)
    def make_uri(node_id):
        safe_id = node_id.replace("-", "_")
        return VBMAPP_INST[safe_id]

    print("🧠 Building the VB-MAPP Knowledge Graph (Nodes and Edges)...")

    # 2. First Pass: Create all Nodes and their internal properties
    for node in vbmapp_data:
        node_uri = make_uri(node["id"])
        
        # Node Type
        if node["type"] == "Domain":
            g.add((node_uri, RDF.type, ECTA_KG.VBMAPP_Domain))
        else: # Milestone or Task
            g.add((node_uri, RDF.type, ECTA_KG.VBMAPP_Milestone))
            
        # Core Properties
        if node.get("title"):
            g.add((node_uri, RDFS.label, Literal(node["title"], lang="en")))
            
        if node.get("domain"):
            g.add((node_uri, ECTA_KG.domain, Literal(node["domain"], lang="en")))
            
        if node.get("level"):
            g.add((node_uri, ECTA_KG.level, Literal(node["level"])))
            
        if node.get("description"):
            g.add((node_uri, ECTA_KG.description, Literal(node["description"], lang="en")))
            
        if node.get("scoring_criteria"):
            g.add((node_uri, ECTA_KG.scoringCriteria, Literal(node["scoring_criteria"], lang="en")))

    # 3. Second Pass: Route the DAG Edges
    for node in vbmapp_data:
        parent_uri = make_uri(node["id"])
        
        # Route SubTasks (Domain -> Milestones)
        for child_id in node.get("hasSubTask", []):
            child_uri = make_uri(child_id)
            g.add((parent_uri, ECTA_KG.hasSubTask, child_uri))
            
        # Route Prerequisites (Milestone -> Previous Milestone)
        for prereq_id in node.get("requiresPrerequisite", []):
            prereq_uri = make_uri(prereq_id)
            g.add((parent_uri, ECTA_KG.requiresPrerequisite, prereq_uri))

    # 4. Serialize to File
    print(f"💾 Serializing to Turtle format...")
    g.serialize(destination=OUTPUT_TTL, format="turtle")
    
    print(f"🎉 Success! Base Ontology generated: {OUTPUT_TTL}")
    print(f"📈 The graph contains {len(g)} triples.")

if __name__ == "__main__":
    main()
