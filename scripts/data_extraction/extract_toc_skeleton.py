import os
import json
import time
import traceback
import google.generativeai as genai
from pypdf import PdfReader, PdfWriter

def call_gemini_single_page(pdf_path: str, prompt: str):
    """Handles upload and extraction for a single page with retries."""
    uploaded_file = None
    for attempt in range(1, 4):
        try:
            uploaded_file = genai.upload_file(pdf_path)
            break
        except Exception as e:
            print(f"      Upload attempt {attempt} failed: {e}")
            time.sleep(5)
            
    if not uploaded_file:
        return []

    try:
        while True:
            file_info = genai.get_file(uploaded_file.name)
            if file_info.state.name == "ACTIVE":
                break
            elif file_info.state.name == "FAILED":
                return []
            time.sleep(2)

        model = genai.GenerativeModel('gemini-3.1-pro-preview')
        for attempt in range(1, 4):
            try:
                response = model.generate_content(
                    [uploaded_file, prompt],
                    generation_config=genai.GenerationConfig(temperature=0.0),
                    request_options={"timeout": 600.0}
                )
        
                raw_text = response.text.strip()
                if "```json" in raw_text:
                    raw_text = raw_text.split("```json")[1].split("```")[0]
                elif "```" in raw_text:
                    raw_text = raw_text.split("```")[1].split("```")[0]
                    
                return json.loads(raw_text.strip())
                
            except Exception as e:
                print(f"      API attempt {attempt} failed: {e}")
                time.sleep(5)
                
    except Exception as e:
        print(f"      Unexpected error: {e}")
        
    finally:
        if uploaded_file:
            try:
                genai.delete_file(uploaded_file.name)
            except Exception:
                pass
            
    return []

def main():
    pdf_path = "scripts/data_extraction/22-cognition-toc.pdf"
    output_json_path = "scripts/data_extraction/22_cognition_skeleton.json"

    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found at {pdf_path}")
        return

    api_key = os.getenv("GEMINI_API_KEY")
    genai.configure(api_key=api_key)

    print(f"Reading TOC PDF {pdf_path}...")
    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)
    
    prompt = """
    You are extracting Table of Contents data from a SINGLE page of a special education curriculum.
    Translate all text to Simplified Chinese.
    
    Output a strictly valid JSON ARRAY of flat objects, one for each "Phasal Objective" (the lowest level, e.g., 1.1, 1.2, 2.1).
    For each item, identify its parent Objective (e.g., "1. 视觉追踪") and parent Submodule (e.g., "知觉篇").
    If the Submodule or Objective header is NOT visible on this specific page (because it started on a previous page), output an empty string "" for it.
    
    JSON SCHEMA:
    [
      {
        "submodule": "string (or empty string)",
        "objective": "string (or empty string)",
        "phasal_index": "string (e.g., '1.1')",
        "phasal_title": "string"
      }
    ]
    """

    master_list = []
    
    # Process page by page
    for p in range(total_pages):
        print(f"\nProcessing TOC Page {p+1}/{total_pages}...")
        temp_pdf = f"scripts/data_extraction/temp_toc_page_{p}.pdf"
        
        writer = PdfWriter()
        writer.add_page(reader.pages[p])
        with open(temp_pdf, "wb") as f_out:
            writer.write(f_out)
            
        page_items = call_gemini_single_page(temp_pdf, prompt)
        
        if page_items:
            print(f"  -> Successfully extracted {len(page_items)} items from page {p+1}.")
            master_list.extend(page_items)
        else:
            print(f"  -> WARNING: Failed to extract data from page {p+1}.")
            
        # Cleanup temp file
        if os.path.exists(temp_pdf):
            os.remove(temp_pdf)

    # Reconstruct the hierarchy (Forward Fill missing parents)
    print("\nReconstructing nested skeleton...")
    current_sub = "未知篇"
    current_obj = "未知目标"
    
    skeleton = {"module": "认知", "submodules": []}
    sub_dict = {}

    for item in master_list:
        if item.get("submodule"): current_sub = item["submodule"]
        if item.get("objective"): current_obj = item["objective"]
        
        p_idx = item.get("phasal_index", "").strip()
        p_title = item.get("phasal_title", "").strip()
        
        if not p_idx: continue # Skip if no index found
        
        if current_sub not in sub_dict:
            sub_dict[current_sub] = {"title": current_sub, "objectives": {}}
            
        if current_obj not in sub_dict[current_sub]["objectives"]:
            sub_dict[current_sub]["objectives"][current_obj] = {"title": current_obj, "phasal_objectives": []}
            
        sub_dict[current_sub]["objectives"][current_obj]["phasal_objectives"].append({
            "index": p_idx,
            "title": p_title
        })

    # Convert dictionaries back to lists for the final JSON
    for sub_k, sub_v in sub_dict.items():
        sub_obj = {"title": sub_v["title"], "objectives": []}
        for obj_k, obj_v in sub_v["objectives"].items():
            sub_obj["objectives"].append({
                "title": obj_v["title"],
                "phasal_objectives": obj_v["phasal_objectives"]
            })
        skeleton["submodules"].append(sub_obj)

    print(f"Saving extracted skeleton to {output_json_path}...")
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(skeleton, f, ensure_ascii=False, indent=4)
        
    print("Done! Skeleton JSON created successfully.")

if __name__ == "__main__":
    main()
