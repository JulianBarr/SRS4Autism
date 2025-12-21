import pandas as pd
from pathlib import Path
from rdflib import Graph, Namespace, Literal

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CSV_PATH = BASE_DIR / "data" / "content_db" / "logic_city_decisions.csv"
KG_PATH = BASE_DIR / "knowledge_graph" / "world_model_complete.ttl"
SRS_KG = Namespace("http://srs4autism.com/schema/")

def apply_fixes():
    if not CSV_PATH.exists():
        print("❌ No CSV found. Use the dashboard to make decisions first.")
        return

    print(f"Loading Graph: {KG_PATH.name}...")
    g = Graph()
    g.parse(KG_PATH, format="turtle")
    
    print(f"Loading Decisions: {CSV_PATH.name}...")
    df = pd.read_csv(CSV_PATH)
    
    print(f"Applying {len(df)} curated tags...")
    
    for _, row in df.iterrows():
        uri = row["Selected_URI"]
        
        # Convert string URI to RDFlib URIRef
        node = None
        # Handle cases where URI might be abbreviated or full
        if uri.startswith("http"):
            from rdflib import URIRef
            node = URIRef(uri)
        
        if node:
            # Add the tag: <node> srs-kg:learningTheme "Logic City"
            g.add((node, SRS_KG.learningTheme, Literal("Logic City")))
            
            # Optional: You could also remove this tag from sibling nodes if you wanted logic to be exclusive
            # But just tagging the winner is usually enough for the filter we wrote.

    print("Saving updated graph...")
    g.serialize(destination=KG_PATH, format="turtle")
    print("✅ Success! Your CSV decisions are now permanently in the graph.")

if __name__ == "__main__":
    apply_fixes()
