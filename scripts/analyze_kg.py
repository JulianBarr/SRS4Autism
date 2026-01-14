import rdflib
from rdflib import Graph, URIRef, Literal
from collections import Counter, defaultdict
import random
import re
import sys

# --- CONFIGURATION ---
KG_FILE_PATH = "knowledge_graph/world_model_complete.ttl"  # Update path if needed
SAMPLE_SIZE = 5

def sanitize_turtle_content(content):
    print("🧹 Sanitizing invalid URIs in memory...")
    
    # Regex to find specific bad pattern: "srs-inst:Stuff With Spaces a srs-kg:Class"
    # It looks for 'srs-inst:' followed by anything until ' a ' or ' ;' or ' .', 
    # capturing cases with spaces/parens which are illegal.
    
    def fix_match(match):
        prefix = match.group(1) # srs-inst:
        bad_id = match.group(2) # The part with spaces
        suffix = match.group(3) # The separator (e.g., ' a ')
        
        # Replace spaces, parens, commas with underscores
        clean_id = re.sub(r'[\s\(\),]', '_', bad_id)
        # Remove consecutive underscores
        clean_id = re.sub(r'_+', '_', clean_id)
        
        return f"{prefix}{clean_id}{suffix}"

    # Pattern: srs-inst:[start]... [bad chars]... [end] (followed by space and predicate/punctuation)
    # We target lines specifically starting with srs-inst or containing it as a subject
    # This is a heuristic patch, not a full parser.
    
    # Matches: srs-inst:Bad Name a ...
    pattern = r'(srs-inst:)([^;\.\n]+?)(\s+a\s+|\s+srs-kg:)'
    
    cleaned_content = re.sub(pattern, fix_match, content)
    return cleaned_content

def analyze_graph(file_path):
    print(f"--- LOADING GRAPH: {file_path} ---")
    g = Graph()
    
    try:
        # Try raw read first to sanitize
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_data = f.read()
        
        # Sanitize
        clean_data = sanitize_turtle_content(raw_data)
        
        # Parse the CLEANED string
        g.parse(data=clean_data, format="turtle")
        print(f"✅ Successfully loaded {len(g)} triples (after sanitization).\n")
        
    except Exception as e:
        print(f"❌ Error loading graph: {e}")
        print("Tip: The file might be too broken for regex patching. Fix the generator logic.")
        return

    # --- ANALYSIS LOGIC (Same as before) ---
    print("--- 1. NAMESPACE & PREFIX ANALYSIS ---")
    ns_counts = Counter()
    for s, p, o in g:
        if isinstance(s, URIRef):
            try: ns_counts[s.n3(g.namespace_manager).split(':')[0]] += 1
            except: pass
    
    print(f"Active Namespaces:")
    for ns, count in ns_counts.most_common(10):
        print(f"  {ns}: {count}")
    print("\n")

    print("--- 2. CLASS DISTRIBUTION ---")
    class_counts = Counter()
    class_members = defaultdict(list)
    
    for s, p, o in g.triples((None, rdflib.RDF.type, None)):
        class_name = o.n3(g.namespace_manager)
        class_counts[class_name] += 1
        class_members[class_name].append(s)

    for cls, count in class_counts.most_common(15):
        print(f"  {cls}: {count} instances")
    print("\n")

    print("--- 3. PREDICATE USAGE (Convention Check) ---")
    top_classes = [c[0] for c in class_counts.most_common(5)]
    
    for cls in top_classes:
        print(f"Analyzing Schema for Class: {cls}")
        properties_used = Counter()
        samples = class_members[cls][:100]
        
        for instance in samples:
            for _, p, o in g.triples((instance, None, None)):
                prop_name = p.n3(g.namespace_manager)
                properties_used[prop_name] += 1
        
        for prop, count in properties_used.most_common():
            print(f"  {prop:<35} | {count}/{len(samples)} samples")
        print("-" * 40)

if __name__ == "__main__":
    analyze_graph(KG_FILE_PATH)
