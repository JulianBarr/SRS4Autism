import sys
import re
from pathlib import Path
from rdflib import Graph, Namespace, RDF

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent
# UPDATED PATH: knowledge_graph/world_model_merged.ttl
INPUT_FILE = BASE_DIR / "knowledge_graph" / "world_model_merged.ttl"

def test_linking_strategy():
    if not INPUT_FILE.exists():
        print(f"❌ CRITICAL: File not found at {INPUT_FILE}")
        return

    print(f"Loading {INPUT_FILE.name}...")
    g = Graph()
    g.parse(INPUT_FILE, format="turtle")
    SRS_KG = Namespace("http://srs4autism.com/schema/")
    print(f"✅ Loaded {len(g)} triples.\n")

    print("--- 1. INDEXING ENGLISH WORDS ---")
    # We create a lookup table:  "processing" -> <http://.../concept-processing>
    # This allows us to instantly check if an English concept exists.
    
    eng_lookup = {}
    
    # Query: Find all English words and the concepts they mean
    q_eng = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    SELECT ?wordLabel ?concept WHERE {
        ?w a srs-kg:Word ;
           srs-kg:text ?wordLabel ;
           srs-kg:means ?concept .
        # Filter for English (heuristic: assuming English words don't have Pinyin or rely on lang tag)
        FILTER (lang(?wordLabel) = "en" || REGEX(STR(?w), "word-en-"))
    }
    """
    for row in g.query(q_eng):
        label = str(row.wordLabel).lower().strip()
        eng_lookup[label] = row.concept

    print(f"Indexed {len(eng_lookup)} English target concepts.")
    if len(eng_lookup) == 0:
        print("⚠️  Warning: Found 0 English words. Check your query filters.")


    print("\n--- 2. SIMULATING 'DICTIONARY GLUE' ---")
    # Since we don't have a real dictionary file loaded, we will test a few HARDCODED examples
    # to prove the logic works. In production, we'd load cedict_ts.u8.
    
    test_cases = [
        ("加工", ["processing", "machining"]),
        ("朋友", ["friend"]),
        ("猫", ["cat"]),
        ("苹果", ["apple"])
    ]
    
    print(f"Testing linking logic on {len(test_cases)} Chinese words...")
    
    matches_found = 0
    
    for zh_word, possible_translations in test_cases:
        # 1. Check if this Chinese word actually exists in your Graph
        q_check_zh = f"""
        PREFIX srs-kg: <http://srs4autism.com/schema/>
        ASK {{
            ?w a srs-kg:Word ;
               srs-kg:text "{zh_word}"@zh .
        }}
        """
        exists = bool(g.query(q_check_zh))
        
        status = "❌ Not in Graph"
        target_concept = "None"
        
        if exists:
            # 2. Try to match translations against our English Index
            status = "⚠️  In Graph, but no English match"
            for en_trans in possible_translations:
                if en_trans in eng_lookup:
                    target_concept = eng_lookup[en_trans]
                    status = f"✅ MATCH! Link to: {target_concept.split('/')[-1]}"
                    matches_found += 1
                    break
        
        print(f"Word: {zh_word:<6} | {status}")

    print("-" * 50)
    if matches_found > 0:
        print("CONCLUSION: Strategy works! We just need to feed it a real dictionary (CC-CEDICT).")
    else:
        print("CONCLUSION: Strategy failed. Either English words are missing or names don't match.")

if __name__ == "__main__":
    test_linking_strategy()