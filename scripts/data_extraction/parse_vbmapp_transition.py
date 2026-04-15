import fitz  # PyMuPDF
import json
import os
import time
import google.generativeai as genai

genai.configure(api_key=os.environ["GEMINI_API_KEY"])

def extract_text_from_pdf(pdf_path, start_page, end_page):
    doc = fitz.open(pdf_path)
    text_chunks = []
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

def parse_vbmapp_transition_chunk(text_chunk, chunk_index):
    prompt = """
    You are an expert ontologist. Your task is to extract the Chapter 7 (The Transition Assessment) of the VB-MAPP.

    Transition Assessment items evaluate a child's readiness for a less restrictive educational setting. 
    They are scored on a 0 to 4 scale.

    Extract the items into a flat JSON array of objects.

    ### JSON SCHEMA PER OBJECT:
    {
      "id": "A unique identifier (e.g., 'trans-milestone-score', 'trans-rate-acquisition')",
      "type": "TransitionItem",
      "title": "The exact title of the category.",
      "description": "What this item assesses.",
      "scoring_criteria": "The 0 to 4 scoring rubric."
    }

    ### RULES:
    1. Output a single, flat JSON array.
    2. Ensure each item captures the full 0-4 scoring logic.

    ### TEXT TO PROCESS:
    """ + text_chunk

    model = genai.GenerativeModel('gemini-3.1-pro-preview') 
    print(f"Sending Transition chunk {chunk_index} to LLM...")
    response = model.generate_content(
        prompt,
        generation_config={"response_mime_type": "application/json"}
    )
    return response.text

if __name__ == "__main__":
    PDF_FILE = "./vbmapp.pdf" 
    # 物理页码 137 到 156 (Chapter 7)
    chunks = extract_text_from_pdf(PDF_FILE, 137, 156)
    
    node_dictionary = {}
    for index, chunk in enumerate(chunks):
        json_output = parse_vbmapp_transition_chunk(chunk, index + 1)
        try:
            parsed_json = json.loads(json_output)
            for node in parsed_json:
                node_id = node.get("id")
                if node_id and node_id not in node_dictionary:
                    node_dictionary[node_id] = node
            time.sleep(5)
        except:
            print(f"Error in chunk {index+1}")

    final_nodes = list(node_dictionary.values())
    with open("vbmapp_transition_master.json", 'w', encoding='utf-8') as f:
        json.dump(final_nodes, f, indent=4, ensure_ascii=False)
    print("Transition Ontology saved to vbmapp_transition_master.json")
