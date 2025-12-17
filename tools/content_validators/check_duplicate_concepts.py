import sys
from pathlib import Path
from rdflib import Graph, Namespace

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent
INPUT_FILE = BASE_DIR / "knowledge_graph" /  "world_model_merged.ttl"

def check_duplicates():
    if not INPUT_FILE.exists():
        print("❌ File not found.")
        return

    print("Loading graph for Duplicate Check...")
    g = Graph()
    g.parse(INPUT_FILE, format="turtle")
    
    # 查找共享同一个 Wikidata ID 的不同 Concept
    query = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    SELECT ?qid (COUNT(DISTINCT ?c) AS ?count) (GROUP_CONCAT(DISTINCT ?c; separator=", ") AS ?uris)
    WHERE {
        ?c a srs-kg:Concept ;
           srs-kg:wikidataId ?qid .
    }
    GROUP BY ?qid
    HAVING (?count > 1)
    ORDER BY DESC(?count)
    LIMIT 20
    """
    
    results = list(g.query(query))
    
    if len(results) > 0:
        print(f"\n⚠️  FOUND {len(results)} WIKIDATA COLLISIONS (The 'Parallel Universe' Issue):")
        print("-" * 60)
        for row in results:
            print(f"Wikidata ID: {row.qid}")
            print(f" -> Shared by {row.count} different concepts:")
            # Split URIs for cleaner display
            uris = str(row.uris).split(", ")
            for uri in uris:
                short_uri = uri.split("/")[-1]
                print(f"      * {short_uri}")
            print("-" * 60)
        print("\n✅ DIAGNOSIS CONFIRMED: You have multiple nodes for the same concept.")
        print("   SOLUTION: We need to merge these nodes into one.")
    else:
        print("\n✅ No duplicates found based on Wikidata ID.")
        print("   (This means the disconnection is due to missing IDs entirely, not duplication.)")

if __name__ == "__main__":
    check_duplicates()