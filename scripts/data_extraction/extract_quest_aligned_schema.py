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

def extract_quest_aligned_schema():
    # 1. 抓取 6 本 JSON 数据
    target_files = glob.glob("2*_ontology_zh_CN.json")
    if not target_files:
        print("❌ 找不到任何 JSON 数据文件！")
        return

    print(f"📦 正在打包 {len(target_files)} 本书的全部临床数据...")
    all_books_data = {}
    for file_path in target_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            all_books_data[file_path.replace("_ontology_zh_CN.json", "")] = json.load(f)

    mega_json_payload = json.dumps(all_books_data, ensure_ascii=False, indent=2)
    
    # 2. 读取主公的完美底座架构 (quest.ttl)
    quest_ttl_path = "quest.ttl"
    if not os.path.exists(quest_ttl_path):
        print(f"❌ 找不到参考底座文件: {quest_ttl_path}")
        return
        
    with open(quest_ttl_path, 'r', encoding='utf-8') as f:
        quest_schema_payload = f.read()

    print("🚀 数据与底座准备完毕！正在发送给拥有超大上下文的 Gemini 大模型...")

    model = genai.GenerativeModel('gemini-3.1-pro-preview')

    # 3. 🎯 全新升级的 Prompt：强制以 Quest.ttl 为核心世界观进行融合提取
    prompt = """
You are an Expert Knowledge Engineer and Special Education Ontology Architect.
Your task is to extract a Unified Ontology Schema (T-Box) from a massive dataset, but you MUST strictly align it with a provided reference architecture.

### 1. THE REFERENCE ARCHITECTURE (YOUR BLUEPRINT)
Below is `quest.ttl`, our core routing engine schema. It uses a Hub-and-Spoke DAG model:
- `Concept` (Hub): Abstract cognitive or physical targets.
- `TeachingTask` / `Quest` (Spoke): Actionable intervention tasks targeting a Concept.
- `requiresPrerequisite`: DAG routing edges between tasks or concepts.

REFERENCE SCHEMA:
```turtle
""" + quest_schema_payload + """
```

### 2. THE RAW DATA (YOUR EVIDENCE)
Below is the massive JSON dataset of the Heep Hong curriculum (6 domains). It has 6 levels (L1 to L6) and contains clinical data like `age_min_months`.

RAW JSON DATA:
```json
""" + mega_json_payload + """
```

### 3. YOUR ARCHITECTURE FUSION TASK:
You must merge the richness of the Heep Hong JSON data into the worldview of `quest.ttl`. 
1. **Map the Levels:** Analyze L1 to L6. Which levels should be mapped as subclasses of `Concept` (e.g., broad domains, categories)? Which levels should be mapped as subclasses of `TeachingTask` or `Quest` (e.g., actionable items, tasks with materials)?
2. **Preserve the DAG Engine:** Keep the properties `targetsConcept`, `requiresPrerequisite`, `conceptPrerequisite` from the reference schema.
3. **Extend with Clinical Properties:** The JSON has new vital data properties. Add `owl:DatatypeProperty` for `ageMinMonths`, `ageMaxMonths`, and `originalLevel` (to store the L1-L6 tag).
4. **Namespace:** Use `hhh-kg: <http://cuma.org/schema/hhh/>` for this new expanded schema.

### 4. OUTPUT REQUIREMENTS:
- DO NOT OUTPUT INSTANCES (A-Box). ONLY OUTPUT THE SCHEMA (T-Box).
- Provide `rdfs:comment` for each class/property explaining how it maps between the JSON levels and the Quest DAG engine.
- Output ONLY valid RDF Turtle syntax. Do not wrap it in markdown blocks.
"""

    # 4. 执行生成 (设定温度为 0，确保严谨融合)
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.0,
            ),
            request_options={"timeout": 600} # 超时时间 10 分钟
        )
        
        ttl_output = response.text

        # 清理可能包含的 markdown 语法
        if ttl_output.startswith("```turtle"): 
            ttl_output = ttl_output[9:]
        elif ttl_output.startswith("```"): 
            ttl_output = ttl_output[3:]
        if ttl_output.endswith("```"): 
            ttl_output = ttl_output[:-3]

        # 5. 保存结果
        output_path = "hhh_quest_aligned_schema.ttl"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(ttl_output.strip())

        print(f"🎉 融合成功！完美的 Hub-and-Spoke 特教大一统蓝图已保存至: {output_path}")

    except Exception as e:
        print(f"❌ 请求大模型时出错: {e}")

if __name__ == "__main__":
    extract_quest_aligned_schema()
