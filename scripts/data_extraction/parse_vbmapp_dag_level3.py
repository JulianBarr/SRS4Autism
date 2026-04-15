import fitz  # PyMuPDF
import json
import os
import time
import google.generativeai as genai

genai.configure(api_key=os.environ["GEMINI_API_KEY"])

def extract_text_from_pdf(pdf_path, start_page, end_page):
    """Extracts pure text from specific physical pages (0-indexed)."""
    doc = fitz.open(pdf_path)
    text_chunks = []
    
    # Process in chunks of 3 pages to avoid overwhelming the LLM
    chunk_size = 3 
    
    for i in range(start_page - 1, end_page, chunk_size):
        chunk_text = ""
        # Make sure we don't go past the end_page
        chunk_end = min(i + chunk_size, end_page)
        
        for j in range(i, chunk_end):
            page = doc.load_page(j)
            chunk_text += f"\n--- PAGE {j+1} ---\n"
            chunk_text += page.get_text("text") + "\n"
            
        text_chunks.append(chunk_text)
        
    return text_chunks

def parse_vbmapp_chunk(text_chunk, chunk_index):
    """Sends a smaller text chunk to Gemini, enforcing JSON output."""
    prompt = """
    You are an expert ontologist and behavioral analyst. Your task is to extract a Directed Acyclic Graph (DAG) ontology from the provided text, which contains Chapter 5 (Level 3) of the VB-MAPP scoring instructions.

    Extract the data into a flat JSON array of objects representing Nodes (Domains, Milestones, Tasks).

    ### JSON SCHEMA PER OBJECT:
    {
      "id": "A unique, lowercase identifier (e.g., 'domain-mand', 'mand-11-m', 'mand-11-a')",
      "type": "Domain" | "Milestone" | "Task",
      "domain": "The standardized Domain name (e.g., 'Mand', 'Tact')",
      "level": 3,
      "title": "The exact title or code (e.g., 'Mand 11-M', '11-a')",
      "description": "The exact description of the skill.",
      "scoring_criteria": "Extract the scoring logic if present (e.g., '1 point: ... 1/2 point: ...'). Leave null for Domains and Tasks without scoring.",
      "hasSubTask": ["Array of IDs representing children nodes."],
      "requiresPrerequisite": ["Array of IDs representing skills that must be mastered first. Infer this from the text if a skill explicitly relies on another. Leave empty [] if none."]
    }

    ### RULES:
    1. DO NOT nest the objects. Output a single, flat JSON array of node objects.
    2. Ensure standard naming for Domains.

    ### TEXT TO PROCESS:
    """ + text_chunk

    model = genai.GenerativeModel('gemini-3.1-pro-preview') 
    
    print(f"Sending chunk {chunk_index} to LLM...")
    
    # Enforce strict JSON output to prevent markdown formatting issues
    response = model.generate_content(
        prompt,
        generation_config={"response_mime_type": "application/json"}
    )
    return response.text

# --- Execution ---
if __name__ == "__main__":
    PDF_FILE = "./vbmapp.pdf" 
    
    # Extract text from physical pages 81 to 107 (Chapter 5 / Level 3)
    print(f"Extracting text from {PDF_FILE} in chunks...")
    chunks = extract_text_from_pdf(PDF_FILE, 81, 107)
    
    # Use a dictionary for deduplication: key = node 'id', value = node object
    node_dictionary = {}
    
    for index, chunk in enumerate(chunks):
        json_output = parse_vbmapp_chunk(chunk, index + 1)
        checkpoint_file = f"vbmapp_level3_checkpoint_{index + 1}.json"
        
        try:
            parsed_json = json.loads(json_output)
            
            # --- DEDUPLICATION & MERGE LOGIC ---
            for node in parsed_json:
                node_id = node.get("id")
                
                if not node_id:
                    continue # Skip invalid nodes
                    
                if node_id in node_dictionary:
                    # Node already exists (e.g., a Domain spanning multiple chunks)
                    existing_node = node_dictionary[node_id]
                    
                    # Merge arrays to ensure we don't lose links
                    if "hasSubTask" in node:
                        merged_subtasks = set(existing_node.get("hasSubTask", []) + node.get("hasSubTask", []))
                        existing_node["hasSubTask"] = list(merged_subtasks)
                        
                    if "requiresPrerequisite" in node:
                        merged_prereqs = set(existing_node.get("requiresPrerequisite", []) + node.get("requiresPrerequisite", []))
                        existing_node["requiresPrerequisite"] = list(merged_prereqs)
                else:
                    # New node, add to dictionary
                    node_dictionary[node_id] = node

            # Save the checkpoint (optional, but good for debugging)
            with open(checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(parsed_json, f, indent=4, ensure_ascii=False)
            print(f"Chunk {index + 1} processed, merged, and saved to {checkpoint_file}")
            
        except json.JSONDecodeError:
            print(f"Error: Chunk {index + 1} did not return valid JSON. Saving raw output.")
            with open(f"vbmapp_level3_error_{index + 1}.txt", 'w', encoding='utf-8') as f:
                f.write(json_output)
        
        print("Sleeping for 5 seconds to respect rate limits...")
        time.sleep(5)

    # Convert the deduplicated dictionary back into a flat array
    final_nodes = list(node_dictionary.values())

    # Save the final combined file
    with open("vbmapp_level3_master.json", 'w', encoding='utf-8') as f:
        json.dump(final_nodes, f, indent=4, ensure_ascii=False)
        
    print("Success! Master DAG Ontology saved to vbmapp_level3_master.json")
