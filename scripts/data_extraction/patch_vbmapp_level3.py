import fitz  # PyMuPDF
import json
import os
import google.generativeai as genai

genai.configure(api_key=os.environ["GEMINI_API_KEY"])

def extract_text_from_pdf(pdf_path, start_page, end_page):
    doc = fitz.open(pdf_path)
    text = ""
    for i in range(start_page - 1, end_page):
        page = doc.load_page(i)
        text += f"\n--- PAGE {i+1} ---\n"
        text += page.get_text("text") + "\n"
    return text

def parse_missing_chunk(text_chunk):
    prompt = """
    You are an expert ontologist. Extract a Directed Acyclic Graph (DAG) ontology from this final section of Chapter 5 (Level 3) of VB-MAPP.
    This section should contain the final Math milestones (e.g., math-14-m, math-15-m).

    Extract the data into a flat JSON array of objects representing Nodes.

    ### JSON SCHEMA PER OBJECT:
    {
      "id": "A unique, lowercase identifier (e.g., 'math-14-m')",
      "type": "Domain" | "Milestone",
      "domain": "Math",
      "level": 3,
      "title": "The exact title (e.g., 'Math 14-M')",
      "description": "The exact description.",
      "scoring_criteria": "Extract the scoring logic if present.",
      "hasSubTask": [],
      "requiresPrerequisite": []
    }

    ### RULES:
    1. Output ONLY a flat JSON array.
    2. Focus on extracting the remaining milestones.

    ### TEXT TO PROCESS:
    """ + text_chunk

    model = genai.GenerativeModel('gemini-3.1-pro-preview') 
    print("Sending missing pages to LLM...")
    response = model.generate_content(
        prompt,
        generation_config={"response_mime_type": "application/json"}
    )
    return response.text

if __name__ == "__main__":
    PDF_FILE = "./vbmapp.pdf" 
    MASTER_FILE = "vbmapp_level3_master.json"
    
    # 1. 提取被遗漏的最后两页 (108 - 109)
    print(f"Extracting missing pages 108-109 from {PDF_FILE}...")
    missing_text = extract_text_from_pdf(PDF_FILE, 108, 108)
    
    # 2. 调用 LLM 提取 JSON
    json_output = parse_missing_chunk(missing_text)
    
    try:
        new_nodes = json.loads(json_output)
        print(f"Successfully extracted {len(new_nodes)} missing nodes!")
        
        # 3. 读取现有的 Master JSON
        if os.path.exists(MASTER_FILE):
            with open(MASTER_FILE, 'r', encoding='utf-8') as f:
                master_nodes = json.load(f)
                
            # 4. 追加新节点并处理 Domain 的 hasSubTask 关联
            master_nodes.extend(new_nodes)
            
            # 找到 Math Domain，把新提取的 ID 加进它的 hasSubTask 数组里
            math_domain = next((n for n in master_nodes if n.get("id") == "domain-math"), None)
            if math_domain:
                for node in new_nodes:
                    if node.get("type") == "Milestone" and node.get("id") not in math_domain["hasSubTask"]:
                        math_domain["hasSubTask"].append(node.get("id"))

            # 5. 覆盖保存回 Master 文件
            with open(MASTER_FILE, 'w', encoding='utf-8') as f:
                json.dump(master_nodes, f, indent=4, ensure_ascii=False)
            print(f"✅ Patch successful! Master file updated.")
            
        else:
            print(f"Error: Could not find {MASTER_FILE}")
            
    except json.JSONDecodeError:
        print("Error: Did not return valid JSON.")
        print(json_output)
