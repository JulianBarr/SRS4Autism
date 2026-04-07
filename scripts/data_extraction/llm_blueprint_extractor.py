import os
import json
import argparse
import re
from pathlib import Path
from rdflib import Graph, URIRef, Namespace
from rdflib.namespace import RDFS
import google.generativeai as genai
try:
    from dotenv import load_dotenv
    # Load from backend/gemini.env or gemini.env if they exist
    if Path("backend/gemini.env").exists():
        load_dotenv("backend/gemini.env")
    else:
        load_dotenv("gemini.env")
except ImportError:
    pass

# Define Namespaces
HHH_KG = Namespace("http://cuma.org/schema/hhh/")
HHH_INST = Namespace("http://cuma.org/instance/hhh/")

def parse_graph_to_hierarchy(ttl_file: str) -> list:
    """
    Parses a Turtle file and returns a nested dictionary of the L1-L3 hierarchy.
    """
    # Read file content and fix markdown link formatting if present
    # e.g., [http://cuma.org/schema/hhh/](http://cuma.org/schema/hhh/) -> <http://cuma.org/schema/hhh/>
    with open(ttl_file, "r", encoding="utf-8") as f:
        ttl_content = f.read()
    
    ttl_content = re.sub(r'\[(http[^\]]+)\]\(\1\)', r'<\1>', ttl_content)
    
    g = Graph()
    g.parse(data=ttl_content, format="turtle")
    
    # Store nodes by URI
    nodes = {}
    
    # Extract nodes with level L1, L2, L3
    q_nodes = """
    PREFIX hhh-kg: <http://cuma.org/schema/hhh/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?subject ?label ?level ?corpus
    WHERE {
        ?subject hhh-kg:originalLevel ?level .
        FILTER(?level IN ("L1", "L2", "L3"))
        OPTIONAL { ?subject rdfs:label ?label }
        OPTIONAL { ?subject hhh-kg:promptCorpus ?corpus }
    }
    """
    
    for row in g.query(q_nodes):
        subject_uri = str(row.subject)
        nodes[subject_uri] = {
            "uri": subject_uri,
            "name": str(row.label) if row.label else "",
            "level": str(row.level) if row.level else "",
            "description": str(row.corpus) if row.corpus else "",
            "sub_concepts": []
        }
        
    # Extract parent-child relationships using hasSubConcept
    q_rels = """
    PREFIX hhh-kg: <http://cuma.org/schema/hhh/>
    
    SELECT ?parent ?child
    WHERE {
        ?parent hhh-kg:hasSubConcept ?child .
    }
    """
    
    child_to_parent = {}
    
    for row in g.query(q_rels):
        parent_uri = str(row.parent)
        child_uri = str(row.child)
        
        if parent_uri in nodes and child_uri in nodes:
            nodes[parent_uri]["sub_concepts"].append(nodes[child_uri])
            child_to_parent[child_uri] = parent_uri
            
    # Find root nodes (nodes without parents among the extracted set)
    roots = []
    for uri, node in nodes.items():
        if uri not in child_to_parent:
            roots.append(node)
            
    # Build clean hierarchy while avoiding cycles
    def build_tree(node, visited):
        if node["uri"] in visited:
            return None # Cycle detected
            
        visited.add(node["uri"])
        
        result = {
            "name": node["name"],
            "level": node["level"],
            "description": node["description"],
            "sub_concepts": []
        }
        
        for sub in node["sub_concepts"]:
            sub_tree = build_tree(sub, visited.copy())
            if sub_tree:
                result["sub_concepts"].append(sub_tree)
                
        return result
        
    clean_roots = []
    for root in roots:
        tree = build_tree(root, set())
        if tree:
            clean_roots.append(tree)
            
    return clean_roots

def filter_with_gemini(raw_hierarchy: list) -> list:
    """
    Sends the raw hierarchy to Gemini 3.1 Pro Preview for semantic filtering
    and returns the cleaned hierarchy.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set. Please set it before running the script.")
        
    genai.configure(api_key=api_key)
    
    # Strip the description/promptCorpus from the hierarchy to reduce payload size
    def strip_descriptions(nodes):
        stripped = []
        for node in nodes:
            stripped.append({
                "name": node.get("name"),
                "level": node.get("level"),
                "sub_concepts": strip_descriptions(node.get("sub_concepts", []))
            })
        return stripped
        
    optimized_hierarchy = strip_descriptions(raw_hierarchy)
    
    model = genai.GenerativeModel(
        model_name="gemini-3.1-pro-preview",
        system_instruction=(
            "You are an Expert Special Education Curriculum Architect. "
            "Below is a raw extracted taxonomy (L1, L2, L3) from an intervention manual. It contains both real curriculum content (e.g., developmental areas, intervention targets) and administrative book noise (e.g., Prefaces, Acknowledgements, Catalogs, Team Members).\n\n"
            "YOUR TASK:\n"
            "Analyze the node names. Prune all branches that are administrative, introductory, or structural book metadata. Keep ONLY the branches that represent actual pedagogical curriculum, developmental domains, or intervention categories.\n\n"
            "OUTPUT FORMAT:\n"
            "Return a clean, nested JSON array of the valid hierarchy. Example:\n"
            "[\n"
            "  {\n"
            "    \"name\": \"语言\",\n"
            "    \"level\": \"L2\",\n"
            "    \"sub_concepts\": [\n"
            "      { \"name\": \"语言表达\", \"level\": \"L3\" },\n"
            "      { \"name\": \"语言理解\", \"level\": \"L3\" }\n"
            "    ]\n"
            "  }\n"
            "]"
        ),
        generation_config=genai.types.GenerationConfig(
            response_mime_type="application/json",
        )
    )
    
    prompt = json.dumps(optimized_hierarchy, ensure_ascii=False, indent=2)
    print(f"Sending request to Gemini (payload size: {len(prompt)} chars)...", flush=True)
    
    try:
        response = model.generate_content(prompt)
        # Parse the JSON response to ensure it's valid
        clean_hierarchy = json.loads(response.text)
        return clean_hierarchy
    except Exception as e:
        print(f"Error calling Gemini API or parsing response: {e}")
        raise

def main():
    parser = argparse.ArgumentParser(description="Extract and filter curriculum blueprint using LLM.")
    parser.add_argument("input_ttl", help="Path to the input *_abox_cleaned.ttl file")
    parser.add_argument("--output", "-o", default="curriculum_blueprint_llm.json", help="Path to output JSON file")
    args = parser.parse_args()
    
    input_path = Path(args.input_ttl)
    if not input_path.exists():
        print(f"Error: Input file {input_path} does not exist.")
        return
        
    print(f"Parsing TTL file: {input_path}", flush=True)
    raw_hierarchy = parse_graph_to_hierarchy(str(input_path))
    
    if not raw_hierarchy:
        print("No L1/L2/L3 nodes found in the graph.")
        return
        
    print(f"Extracted {len(raw_hierarchy)} root nodes. Filtering with Gemini...", flush=True)
    try:
        clean_hierarchy = filter_with_gemini(raw_hierarchy)
    except Exception as e:
        print(f"Failed during Gemini filtering: {e}")
        return
    
    output_path = Path(args.output)
    # If the provided path is just a filename, output in current directory
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(clean_hierarchy, f, ensure_ascii=False, indent=2)
        
    print(f"Successfully saved cleaned blueprint to {output_path}")

if __name__ == "__main__":
    main()
