import os
import json
import google.generativeai as genai

# 确保你在环境变量中设置了 GEMINI_API_KEY
# export GEMINI_API_KEY="your_api_key_here"
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

def extract_ontology_with_llm(json_path, ttl_schema_path, output_path):
    print(f"🚀 正在启动 Gemini 顶级模型进行智能提炼: {json_path}")
    
    # 读取原始 JSON 数据
    with open(json_path, 'r', encoding='utf-8') as f:
        raw_json_data = f.read()
        
    # 读取你提供的 Schema 定义 (quest.ttl)
    with open(ttl_schema_path, 'r', encoding='utf-8') as f:
        schema_definition = f.read()

    # 初始化模型 (使用最强的 Pro 模型，拥有 200万 Token 上下文，处理 1000 个节点绰绰有余)
    # 你可以根据实际情况改为 "gemini-1.5-pro-latest" 或 "gemini-2.5-pro"
    model = genai.GenerativeModel('gemini-1.5-pro-latest')

    # 👑 为 Gemini 精心打造的 System Prompt
    prompt = f"""
    You are an Expert Knowledge Engineer and Special Education Curriculum Architect.
    Your task is to transform a raw, noisy JSON extraction of a special education curriculum into a clean, hierarchical Knowledge Graph in RDF Turtle format.

    ### 1. TARGET SCHEMA (YOUR BLUEPRINT)
    Below is the ECTA Quest Ontology schema you must strictly follow:
    ```turtle
    {schema_definition}
    ```

    ### 2. DATA CLEANING & INTELLIGENCE RULES (CRITICAL)
    The input JSON contains clinical data mixed with publishing noise. You must use your semantic intelligence to filter it:
    - DROP NOISE: Completely ignore and discard any nodes related to publishing, administration, prefaces, acknowledgments, bibliographies, or author lists (e.g., "出版资讯", "制作团队", "参考书目", "序言", "版权").
    - KEEP CLINICAL: Only retain nodes that represent actual therapeutic modules, cognitive concepts, teaching goals, or specific training activities.

    ### 3. ONTOLOGY MAPPING RULES
    Map the surviving clinical nodes to the ECTA schema:
    - High-level domains and phasal objectives (e.g., "语言", "语言理解", "听从指令") become `ecta-kg:Concept`.
    - Specific, actionable items, especially those with age ranges or specific activities (e.g., "听从单一指令-日常动作") become `ecta-kg:TeachingTask`.
    - Hierarchy: If a TeachingTask falls under a Concept, use `ecta-kg:targetsConcept`. If a Concept is a sub-category of another Concept, use `ecta-kg:conceptPrerequisite` or `rdfs:subClassOf`.
    - DO NOT include the long `prompt_corpus` text in the Turtle file. The schema states rich content lives in the Document DB. Only output `rdfs:label`, `rdf:type`, and object properties.
    - Create safe, URL-encoded URIs for the instances using the `ecta-inst:` namespace. For example, a concept named "语言理解" becomes `ecta-inst:Language_Comprehension` or `ecta-inst:%E8%AF%AD%E8%A8%80%E7%90%86%E8%A7%A3`.

    ### 4. INPUT DATA
    Here is the flat JSON array representing the tree via `parent_name`:
    ```json
    {raw_json_data}
    ```

    ### OUTPUT FORMAT
    Output ONLY valid RDF Turtle (.ttl) syntax. Do not wrap it in markdown code blocks, do not provide conversational explanations. Just the raw Turtle string starting with `@prefix`.
    """

    print("🧠 模型正在进行语义分析与知识图谱构建，这可能需要 1-3 分钟...")
    
    # 调整生成参数，给予较大的输出空间
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=0.1, # 保持极低的温度，确保逻辑严密不产生幻觉
            max_output_tokens=8192, 
        )
    )

    ttl_output = response.text
    
    # 简单清理可能包含的 markdown 语法
    if ttl_output.startswith("```turtle"):
        ttl_output = ttl_output[9:]
    if ttl_output.startswith("```"):
        ttl_output = ttl_output[3:]
    if ttl_output.endswith("```"):
        ttl_output = ttl_output[:-3]

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(ttl_output.strip())

    print(f"✅ 智能提取完成！纯净的 Ontology (.ttl) 已保存至: {output_path}")


if __name__ == "__main__":
    # 确保把 quest.ttl 也放在 data_extraction 目录下，或者修改这里的路径
    input_json = "21_heep_hong_language_ontology_zh_CN.json"
    schema_ttl = "quest.ttl" 
    output_ttl = "heep_hong_language_smart.ttl"
    
    if not os.path.exists(schema_ttl):
        print(f"❌ 找不到 Schema 文件: {schema_ttl}，请确保路径正确。")
    else:
        extract_ontology_with_llm(input_json, schema_ttl, output_ttl)
