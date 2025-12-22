import pandas as pd
from pathlib import Path
from rdflib import Graph, Namespace, Literal, URIRef

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
    
    print(f"Applying {len(df)} curated updates with EXCLUSIVITY...")
    
    updates_count = 0
    renames_count = 0
    untagged_count = 0
    
    for _, row in df.iterrows():
        en_text = str(row["English"]).strip()
        uri = row["Selected_URI"]
        new_text = str(row["Selected_Text"]).strip()
        
        # Target Node
        selected_node = None
        if uri.startswith("http"):
            selected_node = URIRef(uri)
            
        if not selected_node:
            continue

        # --- STEP 1: ENFORCE EXCLUSIVITY (The Fix) ---
        # Find the English Word Node(s) to identify all competing Chinese translations
        en_literals = [Literal(en_text, lang="en"), Literal(en_text)]
        
        for en_lit in en_literals:
            # Find English Word Node: ?enNode srs-kg:text "mother"@en
            for en_node in g.subjects(SRS_KG.text, en_lit):
                # Find Concepts: ?enNode srs-kg:means ?concept
                for concept in g.objects(en_node, SRS_KG.means):
                    # Find ALL Chinese Words for this concept: ?zhNode srs-kg:means ?concept
                    for rival_node in g.subjects(SRS_KG.means, concept):
                        # If this rival has the tag, REMOVE IT
                        if (rival_node, SRS_KG.learningTheme, Literal("Logic City")) in g:
                            if rival_node != selected_node:
                                g.remove((rival_node, SRS_KG.learningTheme, Literal("Logic City")))
                                untagged_count += 1
                                # print(f"  - Untagged rival: {rival_node}")

        # --- STEP 2: APPLY NEW TAG ---
        g.add((selected_node, SRS_KG.learningTheme, Literal("Logic City")))
        updates_count += 1
        
        # --- STEP 3: RENAME (Text Edit) ---
        current_text_node = g.value(selected_node, SRS_KG.text)
        if current_text_node and str(current_text_node) != new_text:
            # Remove old text triple
            g.remove((selected_node, SRS_KG.text, None))
            # Add new text triple
            g.add((selected_node, SRS_KG.text, Literal(new_text, lang="zh")))
            renames_count += 1

    print(f"Stats: {updates_count} tags set, {untagged_count} rivals untagged, {renames_count} words renamed.")
    print("Saving updated graph...")
    g.serialize(destination=KG_PATH, format="turtle")
    print("✅ Success! Graph updated.")

if __name__ == "__main__":
    apply_fixes()
