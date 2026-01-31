#!/usr/bin/env python3
import sys
import os
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

try:
    from backend.database.kg_client import KnowledgeGraphClient
except ImportError as e:
    print(f"Error importing backend modules: {e}")
    sys.exit(1)

try:
    from rdflib import Graph, Namespace
    from rdflib.namespace import RDF, RDFS
    RDFLIB_AVAILABLE = True
except ImportError:
    RDFLIB_AVAILABLE = False
    print("⚠️  Warning: rdflib not available. Fallback to TTL file querying disabled.")

def diagnose_sentences():
    print("Connecting to Knowledge Graph...")
    try:
        client = KnowledgeGraphClient()
    except Exception as e:
        print(f"Failed to connect to Knowledge Graph: {e}")
        sys.exit(1)

    # Check if store is empty and try to load TTL file if needed
    print("Checking if store needs to be loaded...")
    test_query = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    SELECT (COUNT(?s) as ?count) WHERE {
        ?s a srs-kg:Sentence .
    }
    """
    
    try:
        test_result = client.query(test_query)
        test_count = int(test_result["results"]["bindings"][0]["count"]["value"])
        
        if test_count == 0:
            print("⚠️  Store appears empty. Attempting to load TTL file...")
            # Try to find and load the main TTL file
            kg_files = [
                project_root / "knowledge_graph" / "world_model_final_master.ttl",
                project_root / "knowledge_graph" / "world_model_complete.ttl",
                project_root / "knowledge_graph" / "world_model_complete.ttl.1218",
            ]
            
            kg_file = None
            for file in kg_files:
                if file.exists():
                    kg_file = file
                    break
            
            if kg_file:
                print(f"📁 Loading file: {kg_file.name}")
                try:
                    client.load_file(str(kg_file))
                    print("✅ TTL file loaded successfully!")
                except Exception as e:
                    print(f"⚠️  Warning: Could not load TTL file: {e}")
                    print("   Continuing with empty store diagnostics...")
            else:
                print("⚠️  Warning: No TTL file found to load.")
                print("   Continuing with empty store diagnostics...")
    except Exception as e:
        print(f"⚠️  Warning: Could not check store status: {e}")
        print("   Continuing with diagnostics...")

    print("\nRunning diagnostics on srs-kg:Sentence nodes...")
    
    # 1. Total Sentences
    query_total = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    SELECT (COUNT(?s) as ?count) WHERE {
        ?s a srs-kg:Sentence .
    }
    """
    
    # 2. Sentences linked to a Word
    query_linked_word = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    SELECT (COUNT(DISTINCT ?s) as ?count) WHERE {
        ?s a srs-kg:Sentence ;
           srs-kg:containsWord ?w .
    }
    """
    
    # 3. Sentences linked to Grammar
    query_linked_grammar = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    SELECT (COUNT(DISTINCT ?s) as ?count) WHERE {
        ?s a srs-kg:Sentence ;
           srs-kg:illustratesGrammar ?g .
    }
    """
    
    # 4. Orphans
    query_orphans = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?s ?label WHERE {
        ?s a srs-kg:Sentence .
        OPTIONAL { ?s srs-kg:containsWord ?w }
        OPTIONAL { ?s srs-kg:illustratesGrammar ?g }
        OPTIONAL { ?s rdfs:label ?label }
        FILTER (!BOUND(?w) && !BOUND(?g))
    }
    LIMIT 5
    """
    
    # Count Orphans Total
    query_orphans_count = """
    PREFIX srs-kg: <http://srs4autism.com/schema/>
    
    SELECT (COUNT(?s) as ?count) WHERE {
        ?s a srs-kg:Sentence .
        OPTIONAL { ?s srs-kg:containsWord ?w }
        OPTIONAL { ?s srs-kg:illustratesGrammar ?g }
        FILTER (!BOUND(?w) && !BOUND(?g))
    }
    """

    try:
        # Execute queries
        res_total = client.query(query_total)
        total_count = int(res_total["results"]["bindings"][0]["count"]["value"])
        
        # If store is empty, try fallback
        if total_count == 0 and RDFLIB_AVAILABLE:
            print("\n⚠️  Store appears empty. Attempting fallback: Querying TTL file directly...")
            diagnose_from_ttl_file()
            return
        
        res_linked_word = client.query(query_linked_word)
        linked_word_count = int(res_linked_word["results"]["bindings"][0]["count"]["value"])
        
        res_linked_grammar = client.query(query_linked_grammar)
        linked_grammar_count = int(res_linked_grammar["results"]["bindings"][0]["count"]["value"])
        
        res_orphans_count = client.query(query_orphans_count)
        orphans_count = int(res_orphans_count["results"]["bindings"][0]["count"]["value"])
        
        res_orphans_sample = client.query(query_orphans)
        orphans_sample = res_orphans_sample["results"]["bindings"]
        
        # Output Results
        print("\n--- Diagnostic Report: srs-kg:Sentence ---")
        print(f"Total Sentences:      {total_count}")
        print(f"Linked to Word:       {linked_word_count}")
        print(f"Linked to Grammar:    {linked_grammar_count}")
        print(f"Orphaned Sentences:   {orphans_count}")
        
        if orphans_count > 0:
            print(f"\n⚠️ WARNING: High number of orphans detected. Ingestion pipeline may be broken.")
            print(f"   ({orphans_count} out of {total_count} sentences are orphans)")
            
            print("\nSample Orphan Sentences:")
            for i, binding in enumerate(orphans_sample, 1):
                uri = binding["s"]["value"]
                label = binding.get("label", {}).get("value", "No Label")
                print(f"{i}. URI: {uri}")
                print(f"   Label: {label}")
        else:
            print("\n✅ No orphaned sentences found.")
        
        # Always also check TTL file for comparison
        if RDFLIB_AVAILABLE:
            print("\n" + "="*60)
            print("Comparing with TTL file source data...")
            diagnose_from_ttl_file()
            
    except Exception as e:
        print(f"Error executing queries: {e}")
        import traceback
        traceback.print_exc()
        
        # Fallback: Try querying TTL file directly using rdflib
        if RDFLIB_AVAILABLE:
            print("\n🔄 Attempting fallback: Querying TTL file directly...")
            try:
                diagnose_from_ttl_file()
            except Exception as fallback_error:
                print(f"❌ Fallback also failed: {fallback_error}")
                import traceback
                traceback.print_exc()


def diagnose_from_ttl_file():
    """Fallback method: Query TTL file directly using rdflib."""
    if not RDFLIB_AVAILABLE:
        print("❌ rdflib not available for fallback")
        return
    
    # Find TTL file
    kg_files = [
        project_root / "knowledge_graph" / "world_model_complete.ttl.1218",
        project_root / "knowledge_graph" / "world_model_complete.ttl",
        project_root / "knowledge_graph" / "world_model_final_master.ttl",
    ]
    
    kg_file = None
    for file in kg_files:
        if file.exists():
            kg_file = file
            break
    
    if not kg_file:
        print("❌ No TTL file found for fallback query")
        return
    
    print(f"📁 Loading TTL file: {kg_file.name}")
    SRS_KG = Namespace("http://srs4autism.com/schema/")
    
    g = Graph()
    try:
        g.parse(str(kg_file), format="turtle")
        print(f"✅ Loaded {len(g)} triples from TTL file")
    except Exception as e:
        print(f"❌ Failed to parse TTL file: {e}")
        return
    
    # Query using rdflib
    # 1. Total Sentences
    total_sentences = list(g.triples((None, RDF.type, SRS_KG.Sentence)))
    total_count = len(total_sentences)
    
    # 2. Sentences linked to Word
    linked_word_set = set()
    for s, p, o in g.triples((None, SRS_KG.containsWord, None)):
        linked_word_set.add(s)
    linked_word_count = len(linked_word_set)
    
    # 3. Sentences linked to Grammar
    linked_grammar_set = set()
    for s, p, o in g.triples((None, SRS_KG.illustratesGrammar, None)):
        linked_grammar_set.add(s)
    linked_grammar_count = len(linked_grammar_set)
    
    # 4. Orphans
    all_sentence_uris = {s for s, p, o in total_sentences}
    linked_sentences = linked_word_set | linked_grammar_set
    orphan_sentences = all_sentence_uris - linked_sentences
    orphans_count = len(orphan_sentences)
    
    # Get sample orphans
    orphans_sample = []
    for i, sentence_uri in enumerate(list(orphan_sentences)[:5]):
        label = None
        for s, p, o in g.triples((sentence_uri, RDFS.label, None)):
            label = str(o)
            break
        orphans_sample.append({
            "s": {"value": str(sentence_uri)},
            "label": {"value": label} if label else {}
        })
    
    # Output Results
    print("\n--- Diagnostic Report: srs-kg:Sentence (from TTL file) ---")
    print(f"Total Sentences:      {total_count}")
    print(f"Linked to Word:       {linked_word_count}")
    print(f"Linked to Grammar:    {linked_grammar_count}")
    print(f"Orphaned Sentences:   {orphans_count}")
    
    if orphans_count > 0:
        print(f"\n⚠️ WARNING: High number of orphans detected. Ingestion pipeline may be broken.")
        print(f"   ({orphans_count} out of {total_count} sentences are orphans)")
        
        print("\nSample Orphan Sentences:")
        for i, binding in enumerate(orphans_sample, 1):
            uri = binding["s"]["value"]
            label = binding.get("label", {}).get("value", "No Label")
            print(f"{i}. URI: {uri}")
            print(f"   Label: {label}")
    else:
        print("\n✅ No orphaned sentences found.")


if __name__ == "__main__":
    diagnose_sentences()
