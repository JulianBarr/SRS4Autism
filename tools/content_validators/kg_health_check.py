import sys
import time
from pathlib import Path
from rdflib import Graph, Namespace, RDF, RDFS

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent
INPUT_FILE = BASE_DIR / "knowledge_graph" / "world_model_merged.ttl"

def run_structural_audit():
    if not INPUT_FILE.exists():
        print(f"❌ CRITICAL: Could not find {INPUT_FILE}")
        return

    print(f"Loading {INPUT_FILE} for Structural Audit...")
    g = Graph()
    g.parse(INPUT_FILE, format="turtle")
    print(f"✅ Loaded {len(g)} triples.\n")

    SRS_KG = Namespace("http://srs4autism.com/schema/")

    print("=== 1. PINYIN TOPOLOGY CHECK ===")
    # Goal: Determine if Pinyin is a 'String' or a 'Structure'
    # We check if words link to pinyin as a Literal (text) or an Object (node)
    
    # FIX: Renamed ?count to ?total
    q_pinyin_literal = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    SELECT (COUNT(?w) AS ?total) WHERE {
        ?w a srs-kg:Word ;
           srs-kg:pinyin ?p .
        FILTER (isLiteral(?p))
    }
    """
    count_lit = int(list(g.query(q_pinyin_literal))[0].total)
    
    # FIX: Renamed ?count to ?total
    q_pinyin_node = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    SELECT (COUNT(?w) AS ?total) WHERE {
        ?w a srs-kg:Word ;
           srs-kg:pinyin ?p .
        FILTER (isIRI(?p))
    }
    """
    count_node = int(list(g.query(q_pinyin_node))[0].total)

    print(f"  * Words with Pinyin as TEXT Strings:  {count_lit}")
    print(f"  * Words with Pinyin as LINKED Nodes:  {count_node}")
    
    if count_node == 0:
        print("  ⚠️  CONCLUSION: Your KG has NO structural Pinyin. It is just text.")
        print("      (You cannot query for 'all words starting with b' easily)")
    else:
        print("  ✅  CONCLUSION: You have structural Pinyin data.")


    print("\n=== 2. THE 'BRIDGE' CHECK (Cross-Lingual Linking) ===")
    # Goal: See if Concepts actually link Chinese and English together.
    # A "Bridged Concept" has at least 1 Chinese Word AND 1 English Word.
    
    # FIX: Renamed ?count to ?total
    q_bridge = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    SELECT (COUNT(DISTINCT ?c) AS ?total) WHERE {
        ?c a srs-kg:Concept .
        
        # Must have a Chinese Word
        ?w_zh a srs-kg:Word ;
              srs-kg:means ?c .
        # Heuristic: Chinese labels are usually just "zh" or contain chinese chars
        FILTER (lang(?w_zh_label) = "zh" || regex(str(?w_zh), "word-")) 
        
        # Must have an English Word
        ?w_en a srs-kg:Word ;
              srs-kg:means ?c ;
              srs-kg:text ?text_en .
        FILTER (lang(?text_en) = "en" || regex(str(?w_en), "word-en"))
    }
    """
    
    # FIX: Renamed ?count to ?total
    q_concepts_total = "SELECT (COUNT(?c) AS ?total) WHERE { ?c a <http://srs4autism.com/schema/Concept> }"
    total_concepts = int(list(g.query(q_concepts_total))[0].total)
    
    # We will do a simpler check: Avg words per concept
    q_density = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    SELECT ?c (COUNT(?w) as ?word_count) WHERE {
        ?c a srs-kg:Concept .
        ?w srs-kg:means ?c .
    } GROUP BY ?c HAVING (?word_count > 1)
    """
    multi_word_concepts = len(list(g.query(q_density)))
    
    print(f"  * Total Concepts: {total_concepts}")
    print(f"  * Concepts with >1 Word (Potential Bridges): {multi_word_concepts}")
    if total_concepts > 0:
        print(f"  * Connection Rate: {multi_word_concepts/total_concepts*100:.1f}%")
    
    if multi_word_concepts < (total_concepts * 0.1):
        print("  ⚠️  CONCLUSION: Most Concepts are isolated (1 word only).")
        print("      Your graph is likely a list of distinct dictionaries, not a unified web.")


    print("\n=== 3. IMAGE CHAOS CHECK ===")
    # Goal: Find out WHERE images are actually attached.
    
    # FIX: Renamed ?count to ?total
    q_image_hosts = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    SELECT ?hostType (COUNT(?img) AS ?total) WHERE {
        ?img a srs-kg:VisualImage .
        
        { ?host srs-kg:hasVisualization ?img }
        UNION
        { ?img srs-kg:representsConcept ?host }
        
        ?host rdf:type ?hostType .
    }
    GROUP BY ?hostType
    """
    
    print("  * Image Attachment Points:")
    results = list(g.query(q_image_hosts))
    if not results:
        print("    (No images found linked to anything)")
    for row in results:
        type_name = row.hostType.split('/')[-1]
        print(f"    -> Attached to {type_name}: {row.total}")

    # Check for "Floating Images" (Unlinked)
    # FIX: Renamed ?count to ?total
    q_floating = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    SELECT (COUNT(?img) AS ?total) WHERE {
        ?img a srs-kg:VisualImage .
        FILTER NOT EXISTS { ?x srs-kg:hasVisualization ?img }
        FILTER NOT EXISTS { ?img srs-kg:representsConcept ?y }
    }
    """
    floating = int(list(g.query(q_floating))[0].total)
    if floating > 0:
        print(f"    -> ⚠️  UNLINKED (Floating) Images: {floating}")

if __name__ == "__main__":
    run_structural_audit()