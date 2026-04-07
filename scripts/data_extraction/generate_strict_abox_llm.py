import json
import glob
import os
import time
import urllib.parse
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables (e.g., from .env)
load_dotenv()

# Configure API
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("❌ Please set the GEMINI_API_KEY environment variable (can be placed in a .env file)")
    exit(1)

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-3.1-pro-preview')

# Target, Output, Checkpoint files
TARGET_FILE = "21_heep_hong_language_ontology_zh_CN.json"
OUTPUT_FILE = "21_heep_hong_language_strict_abox.ttl"
CHECKPOINT_FILE = "strict_abox_checkpoint.json"

PREFIXES = """@prefix hhh-kg: <http://www.cuma.ai/hhh-kg#> .
@prefix hhh-inst: <http://www.cuma.ai/hhh-inst/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

"""

SCHEMA_LEVELS = {
    "Module": "hasSubmodule",
    "Submodule": "hasLearningFocus",
    "LearningFocus": "hasCurriculumItem",
    "CurriculumItem": "hasTarget",
    "TargetObjective": "hasActivity",
    "ActivitySuggestion": "requiresMaterial",
    "Material": None
}

SYSTEM_PROMPT = """You are an Expert Special Education Knowledge Extractor.
Read the provided raw curriculum text chunks. Your task is to extract the intervention activities and map them STRICTLY into our 7-level relational database schema.

The Schema Hierarchy:
Module -> Submodule -> LearningFocus -> CurriculumItem -> TargetObjective -> ActivitySuggestion -> Material

Rules:
1. Do NOT include administrative noise (Prefaces, Publishing info, Teams). Ignore them completely.
2. Infer the parent-child relationships from the text.
3. Output ONLY a valid JSON array of objects representing the nodes.

Example JSON Output format:
[
  {
    "level": "TargetObjective",
    "name": "发出哭声",
    "parent_name": "发出不同的声音",
    "parent_level": "CurriculumItem",
    "description": "(optional detailed text)"
  }
]"""

def load_checkpoints():
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"⚠️ Checkpoint file corrupted. Resetting.")
            return {}
    return {}

def save_checkpoints(data):
    with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def encode_uri(name):
    # URI Encoding, taking care of spaces and special chars safely
    if not name:
        return ""
    # Use safe='' to encode slashes too, if any
    return urllib.parse.quote(name.strip(), safe='')

def generate_triples(nodes):
    triples = []
    
    # Process all nodes in the output
    if not isinstance(nodes, list):
        print("   ⚠️ Warning: LLM output is not a list. Attempting to parse safely.")
        return ""

    for node in nodes:
        if not isinstance(node, dict):
            continue

        level = node.get("level")
        name = node.get("name")
        parent_name = node.get("parent_name")
        parent_level = node.get("parent_level")
        description = node.get("description", "")
        
        # Validation
        if not name or not level:
            continue
            
        if level not in SCHEMA_LEVELS:
            print(f"   ⚠️ Warning: Extracted level '{level}' is not in standard 7 levels. Skipping node.")
            continue
            
        encoded_name = encode_uri(name)
        
        # Class typing (e.g. hhh-inst:Node a hhh-kg:Module .)
        triples.append(f"hhh-inst:{encoded_name} a hhh-kg:{level} .")
        
        # Label handling - json.dumps safely handles escaping quotes and newlines to valid string literal formatting
        name_literal = json.dumps(name, ensure_ascii=False)
        triples.append(f"hhh-inst:{encoded_name} rdfs:label {name_literal} .")
        
        # Description
        if description:
            desc_literal = json.dumps(description, ensure_ascii=False)
            triples.append(f"hhh-inst:{encoded_name} hhh-kg:description {desc_literal} .")
            
        # Parent relationship
        if parent_name and parent_level:
            if parent_level in SCHEMA_LEVELS:
                predicate = SCHEMA_LEVELS[parent_level]
                if predicate:  # some levels might not have a downward predicate theoretically, but in our schema all but Material do
                    encoded_parent = encode_uri(parent_name)
                    triples.append(f"hhh-inst:{encoded_parent} hhh-kg:{predicate} hhh-inst:{encoded_name} .")
            else:
                print(f"   ⚠️ Warning: Extracted parent_level '{parent_level}' is not valid schema.")
    
    return "\n".join(triples) + "\n\n" if triples else ""

def process_data():
    # Navigate to the script's directory properly so relative paths work from anywhere
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    checkpoints = load_checkpoints()
    start_idx = checkpoints.get(TARGET_FILE, 0)
    
    try:
        with open(TARGET_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ Failed to load target file: {TARGET_FILE}. Error: {e}")
        return
        
    total_nodes = len(data)
    print(f"\n==================================================")
    print(f"📚 Launching Extraction Guerrilla Ops on: {TARGET_FILE}")
    print(f"Total Nodes: {total_nodes} | Starting at Node: {start_idx}")
    
    # Init output file with prefixes if starting from 0
    if start_idx == 0:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(PREFIXES)
            
    chunk_size = 2
    MAX_CHUNK_SIZE = 8
    
    current_idx = start_idx
    
    while current_idx < total_nodes:
        # Prevent chunk from overflowing
        end_idx = min(current_idx + chunk_size, total_nodes)
        current_chunk = data[current_idx:end_idx]
        
        chunk_text = json.dumps(current_chunk, ensure_ascii=False, indent=2)
        
        prompt = f"{SYSTEM_PROMPT}\n\nHere is the raw data chunk:\n{chunk_text}"
        
        print(f"[{current_idx}/{total_nodes}] Processing chunk size {end_idx - current_idx}...", end=" ", flush=True)
        
        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            
            response_text = response.text
            parsed_json = json.loads(response_text)
            
            triples = generate_triples(parsed_json)
            if triples:
                with open(OUTPUT_FILE, 'a', encoding='utf-8') as f:
                    f.write(triples)
                print("✅ Extracted triples")
            else:
                print("⚠️ No valid triples generated (might be noise)")
                
            current_idx = end_idx
            
            checkpoints[TARGET_FILE] = current_idx
            save_checkpoints(checkpoints)
            
            # Increase chunk size for next iteration, cap at MAX_CHUNK_SIZE
            chunk_size = min(chunk_size * 2, MAX_CHUNK_SIZE)
            
            time.sleep(1) # Be nice to the API
            
        except Exception as e:
            error_str = str(e).lower()
            print(f"\n   ❌ Error: {e}")
            
            if "429" in error_str or "quota" in error_str or "too many requests" in error_str:
                print("   ⚠️ 429 Quota Exceeded. Sleeping for 30 seconds...")
                time.sleep(30)
                continue
                
            elif "504" in error_str or "503" in error_str or "timeout" in error_str:
                if chunk_size > 1:
                    print("   ⚠️ Network Error. Halving chunk size and retrying immediately...")
                    chunk_size = max(1, chunk_size // 2)
                    continue
                else:
                    print("   ⚠️ Network Error at chunk_size=1. Sleeping for 15 seconds...")
                    time.sleep(15)
                    continue
            else:
                # Generic content error (e.g. JSON parse error from LLM, Safety Error)
                if chunk_size > 1:
                    print("   ⚠️ Generic Error. Halving chunk size...")
                    chunk_size = max(1, chunk_size // 2)
                    continue
                else:
                    print("   ☠️ Poison chunk detected at size=1. Skipping node...")
                    current_idx += 1
                    checkpoints[TARGET_FILE] = current_idx
                    save_checkpoints(checkpoints)
                    continue

if __name__ == "__main__":
    process_data()
    print("✅ Processing complete!")
