import sys
from pathlib import Path
from rdflib import Graph, Namespace

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent
INPUT_FILE = BASE_DIR / "knowledge_graph"  / "world_model_merged.ttl"

def check_translation_bridge():
    if not INPUT_FILE.exists():
        print("❌ File not found.")
        return

    print("Loading graph to test Translation Bridging...")
    g = Graph()
    g.parse(INPUT_FILE, format="turtle")
    
    # 1. Inspect the "Chinese Concepts" to see what properties they DO have
    print("\n--- INSPECTING A BROKEN CONCEPT ---")
    # We look for the specific concept you pasted to see its guts
    query_inspect = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    SELECT ?p ?o
    WHERE {
        <http://srs4autism.com/schema/concept-%E5%8A%A0%E5%B7%A5-06671401> ?p ?o .
    }
    """
    properties = list(g.query(query_inspect))
    if not properties:
        print("Could not find the specific 'processing' concept. Showing random concept properties instead:")
        query_random = "SELECT ?p ?o WHERE { ?s a <http://srs4autism.com/schema/Concept> . ?s ?p ?o } LIMIT 5"
        properties = list(g.query(query_random))
    
    for row in properties:
        print(f"Property: {row.p.split('/')[-1]}  ->  Value: {row.o}")

    # 2. Check for English Definitions in Chinese Concepts
    # Often Chinese datasets include an English gloss (e.g. definition: "machining; processing")
    # If we have that, we can link it to English words!
    print("\n--- CHECKING FOR ENGLISH GLOSSES ---")
    query_gloss = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    SELECT (COUNT(?c) as ?count) WHERE {
        ?c a srs-kg:Concept .
        # Look for properties that might contain English text
        ?c ?p ?def .
        FILTER (lang(?def) = "en" || REGEX(STR(?def), "[a-zA-Z]{4,}"))
    }
    """
    english_glosses = int(list(g.query(query_gloss))[0].count)
    print(f"Chinese Concepts containing English text: {english_glosses}")
    
    if english_glosses > 0:
        print("✅ GOOD NEWS: We can use these English definitions to 'Bridge' the gap!")
    else:
        print("⚠️  BAD NEWS: Chinese concepts are purely Chinese. We need an external dictionary to link them.")

if __name__ == "__main__":
    check_translation_bridge()