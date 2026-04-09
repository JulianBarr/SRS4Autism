import os
import json
import time
import google.generativeai as genai
from dotenv import load_dotenv
from pypdf import PdfReader, PdfWriter

def call_gemini(pdf_path: str, prompt: str, max_gen_attempts: int = 3):
    """Helper function to handle upload, extraction, and cleanup. 
    Allows custom retry limits for generation."""
    uploaded_file = None
    upload_max_attempts = 3
    for attempt in range(1, upload_max_attempts + 1):
        try:
            uploaded_file = genai.upload_file(pdf_path)
            break
        except Exception as e:
            print(f"      Upload attempt {attempt} failed: {e}")
            time.sleep(5)
            
    if not uploaded_file:
        return None

    try:
        model = genai.GenerativeModel('gemini-3.1-pro-preview')
        for attempt in range(1, max_gen_attempts + 1):
            try:
                response = model.generate_content(
                    [uploaded_file, prompt],
                    generation_config=genai.GenerationConfig(temperature=0.0),
                    request_options={"timeout": 600.0}
                )
        
                raw_text = response.text.strip()
                if raw_text.startswith("```json"):
                    raw_text = raw_text[7:]
                elif raw_text.startswith("```"):
                    raw_text = raw_text[3:]
                
                if raw_text.endswith("```"):
                    raw_text = raw_text[:-3]
                    
                return json.loads(raw_text.strip())
                
            except Exception as e:
                print(f"      API attempt {attempt} failed: {e}")
                if attempt < max_gen_attempts:
                    time.sleep(5)
                
    except Exception as e:
        print(f"      Unexpected error: {e}")
        
    finally:
        if uploaded_file:
            try:
                genai.delete_file(uploaded_file.name)
            except Exception:
                pass
            time.sleep(2)
            
    return None

def process_chunk(chunk_dict: dict, skeleton_content: str, reader: PdfReader, chunks_dir: str):
    chunk_index = chunk_dict['index']
    pdf_chunk_path = chunk_dict['pdf_path']
    output_json_path = chunk_dict['json_path']
    start_page = chunk_dict['start']
    end_page = chunk_dict['end']
    
    if os.path.exists(output_json_path):
        print(f"  Chunk {chunk_index} already processed. Skipping.")
        return

    prompt = (
        "You are a meticulous Special Education data extractor.\n\n"
        "I am providing you with a structural skeleton (JSON) of a curriculum, "
        "and a chunk (a few pages) of the scanned PDF of the actual textbook.\n\n"
        "Your job is to read the textbook pages in this chunk, find ANY Phasal Objective present "
        "in these pages (identify them by their index and title from the skeleton), and extract "
        "its specific training Goals, Materials, Passing Criteria, Precautions, and Activity Suggestions.\n\n"
        "CRITICAL INSTRUCTIONS:\n"
        "- ONLY extract data for objectives that are ACTUALLY PRESENT in this chunk of pages.\n"
        "- The `skeleton_index` must EXACTLY match the \"index\" field in the provided skeleton.\n"
        "- The original text is in Traditional Chinese. Translate your extracted data into Simplified Chinese.\n\n"
        "JSON SCHEMA REQUIREMENT:\n"
        "You MUST output strictly valid JSON that matches this exact structure:\n"
        "{\n"
        "  \"items_found\": [\n"
        "    {\n"
        "      \"skeleton_index\": \"string (e.g. '1.1')\",\n"
        "      \"goals\": [\n"
        "        {\n"
        "          \"description\": \"string\",\n"
        "          \"materials\": [\"string\", \"string\"],\n"
        "          \"passing_criteria\": \"string or null\",\n"
        "          \"precautions\": \"string or null\",\n"
        "          \"activity_suggestions\": \"string or null\"\n"
        "        }\n"
        "      ]\n"
        "    }\n"
        "  ]\n"
        "}\n"
        "If no relevant data is found, output: {\"items_found\": []}\n\n"
        "Here is the structural skeleton for reference:\n"
        f"{skeleton_content}"
    )

    print(f"  Processing chunk {chunk_index} (pages {start_page} to {end_page-1}) with gemini-3.1-pro-preview...")
    
    # FAIL FAST: Only give the 3-page chunk 1 attempt.
    result = call_gemini(pdf_chunk_path, prompt, max_gen_attempts=1)
    
    if result is not None:
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"  Chunk {chunk_index} complete!")
        return

    # THE ADAPTIVE FALLBACK (Immediate pivot)
    print(f"  [!] Chunk {chunk_index} failed on first attempt. Triggering adaptive 1-page fallback...")
    combined_items = []
    
    for p in range(start_page, end_page):
        print(f"    -> Fallback: Extracting single page {p}...")
        single_pdf_path = os.path.join(chunks_dir, f"temp_fallback_page_{p}.pdf")
        
        if not os.path.exists(single_pdf_path):
            writer = PdfWriter()
            writer.add_page(reader.pages[p])
            with open(single_pdf_path, "wb") as f_out:
                writer.write(f_out)
                
        # Give the single pages the full 3 retries
        page_result = call_gemini(single_pdf_path, prompt, max_gen_attempts=3)
        
        if page_result and "items_found" in page_result:
            combined_items.extend(page_result["items_found"])
            print(f"    -> Page {p} succeeded!")
        else:
            print(f"    -> WARNING: Page {p} completely failed. Skipping page.")
            
    # Save the combined fallback data to the original chunk path so caching works
    final_result = {"items_found": combined_items}
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(final_result, f, ensure_ascii=False, indent=2)
    print(f"  Chunk {chunk_index} fallback complete! Saved successfully.")


def main():
    load_dotenv()
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY environment variable not found.")
        return
    genai.configure(api_key=api_key)
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    skeleton_path = os.path.join(base_dir, "23_self_care_skeleton.json")
    pdf_path = os.path.join(base_dir, "23-self-care.pdf")
    output_path = os.path.join(base_dir, "23_self_care_enriched_abox.json")
    
    chunks_dir = os.path.join(base_dir, "temp_chunks")
    os.makedirs(chunks_dir, exist_ok=True)
    
    print(f"Loading skeleton from {skeleton_path}...")
    with open(skeleton_path, 'r', encoding='utf-8') as f:
        skeleton_content = f.read()
        skeleton_dict = json.loads(skeleton_content)
        
    print(f"Reading PDF {pdf_path}...")
    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)
    chunk_size = 3
    
    print(f"Total pages: {total_pages}. Splitting into chunks of {chunk_size} pages...")
    
    chunk_files = []
    for start_page in range(0, total_pages, chunk_size):
        end_page = min(start_page + chunk_size, total_pages)
        chunk_index = start_page // chunk_size
        chunk_pdf_path = os.path.join(chunks_dir, f"chunk_{chunk_index}.pdf")
        chunk_json_path = os.path.join(chunks_dir, f"chunk_{chunk_index}.json")
        
        chunk_files.append({
            "index": chunk_index,
            "pdf_path": chunk_pdf_path,
            "json_path": chunk_json_path,
            "start": start_page,
            "end": end_page
        })
        
        if not os.path.exists(chunk_pdf_path):
            writer = PdfWriter()
            for i in range(start_page, end_page):
                writer.add_page(reader.pages[i])
            with open(chunk_pdf_path, "wb") as f_out:
                writer.write(f_out)
                
    for chunk in chunk_files:
        process_chunk(chunk, skeleton_content, reader, chunks_dir)
        
    print("Merging results...")
    extracted_items_by_index = {}
    
    for chunk in chunk_files:
        if os.path.exists(chunk['json_path']):
            with open(chunk['json_path'], 'r', encoding='utf-8') as f:
                try:
                    chunk_data = json.load(f)
                    items = chunk_data.get("items_found", [])
                    for item in items:
                        index = item.get("skeleton_index")
                        if not index:
                            continue
                        goals = item.get("goals", [])
                        if index not in extracted_items_by_index:
                            extracted_items_by_index[index] = []
                        extracted_items_by_index[index].extend(goals)
                except json.JSONDecodeError:
                    print(f"Warning: Could not decode JSON from {chunk['json_path']}")
                    
    print("Mapping to skeleton...")
    for sub in skeleton_dict.get("submodules", []):
        for obj in sub.get("objectives", []):
            for phasal in obj.get("phasal_objectives", []):
                index = phasal.get("index")
                if index in extracted_items_by_index:
                    phasal["goals"] = extracted_items_by_index[index]
                else:
                    phasal["goals"] = [] 
                    
    print(f"Extraction complete! Saving to {output_path}...")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(skeleton_dict, f, ensure_ascii=False, indent=2)
        
    print("Done!")

if __name__ == '__main__':
    main()
