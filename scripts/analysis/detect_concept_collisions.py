import requests
import csv
import sys
from pathlib import Path

# --- CONFIGURATION ---
FUSEKI_ENDPOINT = "http://localhost:3030/srs4autism/query"
OUTPUT_FILE = Path("logs/concept_collisions_report.csv")

def detect_collisions():
    print("🕵️  Scanning Knowledge Graph for Ambiguous Concepts...")
    
    # Query: Find English words that link to MULTIPLE Chinese words
    # We group by the English word and count distinct Chinese translations
    sparql_query = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    
    SELECT ?englishWord (GROUP_CONCAT(DISTINCT ?chineseWord; separator="|") AS ?candidates) (COUNT(DISTINCT ?chineseWord) AS ?count)
    WHERE {
        # 1. Find English Word
        ?enNode a srs-kg:Word ;
                srs-kg:text ?englishWord .
        FILTER(lang(?englishWord) = "en")
        
        # 2. Follow path to Concept
        ?enNode srs-kg:means ?concept .
        
        # 3. Follow path from Concept to Chinese Word
        ?zhNode srs-kg:means ?concept ;
                srs-kg:text ?chineseWord .
        FILTER(lang(?chineseWord) = "zh")
        
        # Exclude self-loops or empty strings if any
        FILTER(?englishWord != "")
        FILTER(?chineseWord != "")
    }
    GROUP BY ?englishWord
    HAVING (COUNT(DISTINCT ?chineseWord) > 1)
    ORDER BY DESC(?count)
    """

    try:
        response = requests.post(
            FUSEKI_ENDPOINT, 
            data={"query": sparql_query}, 
            headers={"Accept": "application/sparql-results+json"}
        )
        response.raise_for_status()
        results = response.json().get("results", {}).get("bindings", [])
    except Exception as e:
        print(f"❌ Error connecting to Fuseki: {e}")
        return

    if not results:
        print("✅ No collisions found! (Or graph is empty)")
        return

    # Ensure output directory exists
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    print(f"⚠️  Found {len(results)} ambiguous concepts.")
    
    # Write to CSV
    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["English Word", "Collision Count", "Candidates (Pipe Separated)", "Action Needed"])
        
        for row in results:
            english = row["englishWord"]["value"]
            count = row["count"]["value"]
            candidates = row["candidates"]["value"]
            
            # Simple heuristic for "Action Needed"
            action = "Check Polysemy"
            if int(count) > 5:
                action = "Likely Garbage/Stopword"
            
            writer.writerow([english, count, candidates, action])
            
            # Print preview of first 5
            if results.index(row) < 5:
                print(f"   • {english}: {candidates.replace('|', ', ')}")

    print(f"\n📄 Report generated: {OUTPUT_FILE}")
    print("   Open this file to decide which words need 'Logic City' tagging or Graph splitting.")

if __name__ == "__main__":
    detect_collisions()
