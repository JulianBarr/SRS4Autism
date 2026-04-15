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
    
    # 障碍章节的文字非常密集，我们用 4 页一个 Chunk 以保证大模型能抓到完整的 0-4 计分标准
    chunk_size = 4 
    
    for i in range(start_page - 1, end_page, chunk_size):
        chunk_text = ""
        chunk_end = min(i + chunk_size, end_page)
        
        for j in range(i, chunk_end):
            page = doc.load_page(j)
            chunk_text += f"\n--- PAGE {j+1} ---\n"
            chunk_text += page.get_text("text") + "\n"
            
        text_chunks.append(chunk_text)
        
    return text_chunks

def parse_vbmapp_barriers_chunk(text_chunk, chunk_index):
    """Sends a smaller text chunk to Gemini, enforcing JSON output for Barriers."""
    prompt = """
    You are an expert ontologist and behavioral analyst. Your task is to extract a Directed Acyclic Graph (DAG) ontology from the provided text, which contains Chapter 6 (The Barriers Assessment) of the VB-MAPP.

    Unlike milestones, Barriers are negative behaviors or missing skills that impede learning. They are scored on a 0 to 4 scale (0 = no barrier, 4 = severe barrier).

    Extract the 24 Barriers into a flat JSON array of objects representing Nodes.

    ### JSON SCHEMA PER OBJECT:
    {
      "id": "A unique, lowercase identifier (e.g., 'barrier-negative-behavior', 'barrier-prompt-dependent')",
      "type": "Barrier",
      "title": "The exact title of the barrier (e.g., 'Negative Behavior', 'Prompt Dependent')",
      "description": "A brief description of what this barrier entails.",
      "scoring_criteria": "Extract the explicit 0 to 4 scoring logic (e.g., '0 score: ... 1 score: ... 2 score: ... 3 score: ... 4 score: ...')"
    }

    ### RULES:
    1. DO NOT nest the objects. Output a single, flat JSON array of node objects.
    2. Focus specifically on extracting the 24 main categories of barriers and their 0-4 scoring rubrics.

    ### TEXT TO PROCESS:
    """ + text_chunk

    model = genai.GenerativeModel('gemini-3.1-pro-preview') 
    
    print(f"Sending chunk {chunk_index} to LLM...")
    
    response = model.generate_content(
        prompt,
        generation_config={"response_mime_type": "application/json"}
    )
    return response.text

# --- Execution ---
if __name__ == "__main__":
    PDF_FILE = "./vbmapp.pdf" 
    
    # 提取物理页码 109 到 136 (Chapter 6: Barriers Assessment)
    print(f"Extracting Barriers Assessment from {PDF_FILE} in chunks...")
    chunks = extract_text_from_pdf(PDF_FILE, 109, 136)
    
    node_dictionary = {}
    
    for index, chunk in enumerate(chunks):
        json_output = parse_vbmapp_barriers_chunk(chunk, index + 1)
        checkpoint_file = f"vbmapp_barriers_checkpoint_{index + 1}.json"
        
        try:
            parsed_json = json.loads(json_output)
            
            for node in parsed_json:
                node_id = node.get("id")
                if not node_id:
                    continue 
                    
                if node_id not in node_dictionary:
                    node_dictionary[node_id] = node

            with open(checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(parsed_json, f, indent=4, ensure_ascii=False)
            print(f"Chunk {index + 1} processed and saved to {checkpoint_file}")
            
        except json.JSONDecodeError:
            print(f"Error: Chunk {index + 1} did not return valid JSON. Saving raw output.")
            with open(f"vbmapp_barriers_error_{index + 1}.txt", 'w', encoding='utf-8') as f:
                f.write(json_output)
        
        print("Sleeping for 5 seconds to respect rate limits...")
        time.sleep(5)

    final_nodes = list(node_dictionary.values())

    # 保存最终完整的障碍图谱
    with open("vbmapp_barriers_master.json", 'w', encoding='utf-8') as f:
        json.dump(final_nodes, f, indent=4, ensure_ascii=False)
        
    print("Success! Barriers Ontology saved to vbmapp_barriers_master.json")
