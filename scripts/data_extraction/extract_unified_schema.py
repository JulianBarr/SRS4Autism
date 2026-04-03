import os
import json
import glob
import google.generativeai as genai

# 确保环境变量中配置了 API KEY
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("❌ 请先设置环境变量 GEMINI_API_KEY")
    exit(1)

genai.configure(api_key=api_key)

def extract_unified_schema():
    # 1. 抓取所有 6 本已经转为简体的核心 JSON
    target_files = glob.glob("2*_ontology_zh_CN.json")
    if not target_files:
        print("❌ 找不到任何 2*_ontology_zh_CN.json 文件！")
        return

    print(f"📦 正在打包 {len(target_files)} 本书的全部临床数据...")
    
    # 将 6 本书的数据组装成一个巨大的字典，让模型知道数据来源
    all_books_data = {}
    total_nodes = 0
    for file_path in target_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            book_name = file_path.replace("_ontology_zh_CN.json", "")
            all_books_data[book_name] = data
            total_nodes += len(data)

    # 转化为字符串 Payload
    mega_json_payload = json.dumps(all_books_data, ensure_ascii=False, indent=2)
    payload_size_mb = len(mega_json_payload.encode('utf-8')) / (1024 * 1024)
    
    print(f"✅ 打包完毕！共计 {total_nodes} 个节点，数据体积约 {payload_size_mb:.2f} MB。")
    print("🚀 正在将这头“巨兽”喂给拥有 200万 Token 上下文的大模型，请耐心等待 (可能需要 2-5 分钟)...")

    # 2. 调用拥有长上下文的 Pro 模型
    # gemini-1.5-pro / gemini-2.5-pro 均支持 200 万 token
    model = genai.GenerativeModel('gemini-2.5-pro')

    # 3. 🎯 超级 Prompt：逼迫 LLM 进行全局本体抽象
    prompt = f"""
    You are an Expert Knowledge Engineer and Ontology Architect for Special Education.
    Your task is to perform a BOTTOM-UP ontology extraction based on a massive, combined dataset covering 6 domains of early childhood intervention (Language, Cognition, Motor Skills, etc.).

    I am providing you with the full JSON extraction of all 6 books. 

    ### YOUR ANALYSIS TASK:
    1. Look at the holistic structure across ALL domains. Do they share a common hierarchical pattern (L1 to L6)? What does each level represent conceptually across the entire curriculum?
    2. Identify the core entities: What is a "Domain"? What is a "Category"? What is a "Clinical Objective" (usually bound by age ranges)? What is an "Intervention Activity" (rich instructional text)?
    3. Ignore publishing noise ("出版资讯", "制作团队", "版权", "参考书目"). Focus ONLY on the therapeutic and developmental structure.

    ### YOUR OUTPUT REQUIREMENT:
    Generate a UNIFIED formal RDF Turtle (.ttl) file that defines the Schema (Classes, Object Properties, Datatype Properties) for this entire curriculum.
    
    - Define `owl:Class` for the different levels of abstraction.
    - Define `owl:ObjectProperty` for the topological relationships (e.g., parent-child, prerequisite).
    - Define `owl:DatatypeProperty` for properties like minimum/maximum age, and document DB references (since rich text shouldn't pollute the graph).
    - Use the namespace `hhh: <http://cuma.org/ontology/hhh#>`
    - Provide `rdfs:comment` for each definition explaining your rationale based on the provided JSON.

    ### CRITICAL:
    - DO NOT OUTPUT INSTANCES (A-Box). ONLY OUTPUT THE SCHEMA (T-Box).
    - Output ONLY valid RDF Turtle syntax. Do not wrap it in markdown blocks.

    Here is the MEGA JSON data for the entire curriculum:
    {mega_json_payload}
    """

    # 4. 执行生成 (降低 temperature 确保逻辑严谨，防止胡编乱造)
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.0,
            ),
            request_options={"timeout": 600} # 巨型 payload 可能需要较长响应时间，设置为 10 分钟超时
        )
        
        ttl_output = response.text

        # 简单清理可能包含的 markdown 语法
        if ttl_output.startswith("```turtle"): 
            ttl_output = ttl_output[9:]
        elif ttl_output.startswith("```"): 
            ttl_output = ttl_output[3:]
        if ttl_output.endswith("```"): 
            ttl_output = ttl_output[:-3]

        # 5. 保存结果
        output_path = "hhh_unified_schema.ttl"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(ttl_output.strip())

        print(f"🎉 史诗级任务完成！大一统的 Ontology Schema 已成功生成并保存至: {output_path}")

    except Exception as e:
        print(f"❌ 请求大模型时出错: {e}")

if __name__ == "__main__":
    extract_unified_schema()
