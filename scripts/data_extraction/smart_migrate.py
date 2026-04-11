import os
import json
import time
import google.generativeai as genai
from dotenv import load_dotenv

def clean_node_with_llm(model, raw_goals_data, phasal_title):
    """把旧的混乱 goals 数组交给大模型重新整理"""
    prompt = f"""
    [CLINICAL/MEDICAL CONTEXT: This text is extracted from a certified Special Education and Pediatric Occupational Therapy (OT) manual. It describes Activities of Daily Living (ADL), including feeding, swallowing, and toileting training for children with developmental delays. All bodily functions described are in a strict clinical and educational context.]
    
    You are an expert clinical data cleaner. I have extracted some pediatric OT curriculum data, but it is a mess. 
    Some data is duplicated, some is merged, and the age groups are stuck inside the descriptions.
    
    Phasal Objective Title: "{phasal_title}"
    
    Here is the messy data:
    {json.dumps(raw_goals_data, ensure_ascii=False)}
    
    Please reformat this data into a clean "Target Set" structure.
    1. Extract all unique materials into a single `shared_materials` array.
    2. Extract all unique precautions into a single `shared_precautions` string.
    3. Extract all unique activity suggestions into a single `shared_activity_suggestions` array.
    4. Isolate the specific training goals into `sub_goals`. Separate any label (A, B, C) and age group (e.g., "0-6 个月") from the description.
    
    Respond ONLY with valid JSON matching this exact schema:
    {{
        "shared_materials": ["string"],
        "shared_precautions": "string or empty",
        "shared_activity_suggestions": ["string"],
        "sub_goals": [
            {{
                "label": "string (e.g., 'A', 'B', or null)",
                "age_group": "string (e.g., '0-6 个月' or null)",
                "description": "string (cleaned description)"
            }}
        ]
    }}
    """
    
    for attempt in range(3):
        try:
            # ✨ 加入 Safety Settings，强制放行所有特教敏感词汇
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(temperature=0.0),
                safety_settings=[
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
                ]
            )
            raw_text = response.text.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:-3]
            elif raw_text.startswith("```"):
                raw_text = raw_text[3:-3]
                
            return json.loads(raw_text.strip())
        except Exception as e:
            print(f"      [重试 {attempt+1}/3] AI 清洗失败: {e}")
            time.sleep(2)
            
    return None

def main():
    load_dotenv()
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    
    # 使用最高性价比的 Flash Lite 模型
    model = genai.GenerativeModel('gemini-3.1-flash-lite-preview') 
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(base_dir, "23_self_care_enriched_abox.json")
    output_file = os.path.join(base_dir, "23_self_care_enriched_abox_v2.json")
    
    # ==========================================
    # ✨ Checkpointing: 优先读取进度存档
    # ==========================================
    if os.path.exists(output_file):
        print(f"🔄 发现存档文件，执行断点续传...")
        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        print(f"🚀 开始全新清洗: {input_file}")
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

    # 遍历所有节点
    for sub in data.get("submodules", []):
        for obj in sub.get("objectives", []):
            for phasal in obj.get("phasal_objectives", []):
                
                # 只有存在旧的 "goals" 字段，才说明这个节点还没被洗过
                if "goals" in phasal and len(phasal["goals"]) > 0:
                    print(f"  正在清洗节点: {phasal.get('index')} {phasal.get('title')} ...")
                    
                    cleaned_data = clean_node_with_llm(model, phasal["goals"], phasal.get("title"))
                    
                    if cleaned_data:
                        # 替换数据并销毁旧标识
                        phasal["shared_materials"] = cleaned_data.get("shared_materials", [])
                        phasal["shared_precautions"] = cleaned_data.get("shared_precautions", "")
                        phasal["shared_activity_suggestions"] = cleaned_data.get("shared_activity_suggestions", [])
                        phasal["sub_goals"] = cleaned_data.get("sub_goals", [])
                        del phasal["goals"]  # 彻底删掉烂摊子
                        
                        # ==========================================
                        # ✨ Checkpointing: 实时存盘
                        # ==========================================
                        with open(output_file, 'w', encoding='utf-8') as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                            
                    else:
                        print(f"  ⚠️ 警告: 节点 {phasal.get('index')} 清洗失败，保留原样。")

    print(f"\n🎉 恭喜！全部节点清洗完毕！已保存至: {output_file}")

if __name__ == '__main__':
    main()
