import os
import json
import google.generativeai as genai

# 确保环境变量中配置了 API KEY
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("❌ 请先设置环境变量 GEMINI_API_KEY")
    exit(1)

genai.configure(api_key=api_key)

def extract_schema():
    input_file = "21_heep_hong_language_ontology_zh_CN.json"
    
    if not os.path.exists(input_file):
        print(f"❌ 找不到文件: {input_file}")
        return

    # 1. 读取真实跑出来的一本书的 JSON (作为 LLM 归纳的样本)
    with open(input_file, 'r', encoding='utf-8') as f:
        # 截取前 300 个节点，足够 LLM 看清树状结构和各种层级的数据特征
        raw_data = json.load(f)[:300] 
        json_sample = json.dumps(raw_data, ensure_ascii=False, indent=2)

    print(f"🚀 正在将 {input_file} 的数据样本发送给 Gemini 3.1 Pro，等待其抽象 Ontology Schema...")

    # 2. 调用主公指定的 3.1 预览版模型
    model = genai.GenerativeModel('gemini-3.1-pro-preview')

    # 3. 🎯 核心 Prompt：逼迫 LLM 根据真实数据抽象骨架 (T-Box)
    prompt = f"""
    You are an Expert Knowledge Engineer and Ontology Architect for Special Education.
    Your task is to perform a BOTTOM-UP ontology extraction. I will provide you with a JSON array representing a hierarchical Special Education curriculum.

    DO NOT guess or invent an ontology. You MUST analyze the provided JSON and abstract its underlying Schema (T-Box).

    ### YOUR ANALYSIS TASK:
    1. Look at the `level` fields (L1, L2, L3, L4, L5, L6). What semantic concept does each level represent in this specific book? (e.g., Is L1 a "Domain"? Is L3 a "Milestone"? Is L5 an "Intervention Task"? Is L6 "Materials"?)
    2. Look at the data properties. Which nodes contain `age_min_months`? Which nodes contain rich `prompt_corpus` with instructional steps?
    3. Look at the `parent_name` topology. How do these classes relate to each other hierarchically?
    4. Ignore publishing noise (nodes about "出版资讯", "版权", "序言"). Focus only on the therapeutic structure.

    ### YOUR OUTPUT REQUIREMENT:
    Based strictly on your analysis of the JSON, generate a formal RDF Turtle (.ttl) file that defines the Schema (Classes, Object Properties, Datatype Properties).
    
    - Define `owl:Class` for the different levels of abstraction you discovered.
    - Define `owl:ObjectProperty` for the parent-child relationships between these classes.
    - Define `owl:DatatypeProperty` for attributes like age limits or instructional text.
    - Use the namespace `hhh: <http://cuma.org/ontology/hhh#>`
    - Provide `rdfs:comment` for each class/property explaining WHY you defined it this way based on the JSON data.

    ### CRITICAL:
    DO NOT OUTPUT INSTANCES (A-Box). ONLY OUTPUT THE SCHEMA (T-Box).
    Output ONLY valid RDF Turtle syntax. Do not wrap it in markdown code blocks.

    Here is the JSON data sample from the book:
    {json_sample}
    """

    # 4. 执行生成 (降低 temperature 确保逻辑严密)
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.0,
            ),
            request_options={"timeout": 120}
        )
        
        ttl_output = response.text

        # 清理可能附带的 markdown 标记
        if ttl_output.startswith("```turtle"): 
            ttl_output = ttl_output[9:]
        elif ttl_output.startswith("```"): 
            ttl_output = ttl_output[3:]
        if ttl_output.endswith("```"): 
            ttl_output = ttl_output[:-3]

        # 5. 保存结果
        output_path = "heep_hong_extracted_schema.ttl"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(ttl_output.strip())

        print(f"✅ 智能抽取的 Ontology Schema 已保存至: {output_path}")
        print("🎯 请主公查阅该文件，看看大模型从你的真实数据中领悟出了怎样的骨架！")

    except Exception as e:
        print(f"❌ 请求大模型时出错: {e}")

if __name__ == "__main__":
    extract_schema()
