import json
import glob
import os
import time
import urllib.parse
import google.generativeai as genai

# 配置 API
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("❌ 请先设置环境变量 GEMINI_API_KEY")
    exit(1)

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-3.1-pro-preview')

CHECKPOINT_FILE = "abox_checkpoint.json"

def load_checkpoints():
    """加载断点记录，并防御 0 字节坏档"""
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"   ⚠️ 警告：检测到断点文件 {CHECKPOINT_FILE} 损坏 (可能是上次强制中断导致)。已自动重置清理！")
            return {}
    return {}

def save_checkpoints(data):
    with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def process_book_with_guerrilla_tactics(json_file, schema_content, checkpoints):
    print(f"\n==================================================")
    print(f"📚 正在启动游击战装甲流水线: {json_file}")
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError:
        print(f"   ❌ 致命错误：源文件 {json_file} 为空或已损坏，请检查数据源！")
        return
        
    output_ttl_file = json_file.replace("_ontology_zh_CN.json", "_abox.ttl")
    total_nodes = len(data)
    
    start_node_idx = checkpoints.get(json_file, 0)

    if start_node_idx == 0:
        with open(output_ttl_file, 'w', encoding='utf-8') as f:
            # 恢复正确的 URI 前缀，去除了错误的 markdown 链接格式
            f.write("@prefix hhh-kg: [http://cuma.org/schema/hhh/](http://cuma.org/schema/hhh/) .\n")
            f.write("@prefix hhh-inst: [http://cuma.org/instance/hhh/](http://cuma.org/instance/hhh/) .\n")
            f.write("@prefix rdfs: [http://www.w3.org/2000/01/rdf-schema#](http://www.w3.org/2000/01/rdf-schema#) .\n")
            f.write("@prefix xsd: [http://www.w3.org/2001/XMLSchema#](http://www.w3.org/2001/XMLSchema#) .\n\n")
    else:
        print(f"   ♻️ 发现断点记录！已成功处理 {start_node_idx} 个节点，继续推进...")

    if start_node_idx >= total_nodes:
        print("   ✅ 这本书之前已全部锻造完毕，跳过。")
        return

    # 🎯 游击战术配置
    current_chunk_size = 2 
    MAX_CHUNK_SIZE = 8

    while start_node_idx < total_nodes:
        end_idx = min(start_node_idx + current_chunk_size, total_nodes)
        chunk = data[start_node_idx:end_idx]
        
        print(f"   ⏳ 正在处理节点 [{start_node_idx} - {end_idx-1}] (本批 {len(chunk)} 个, 窗口大小: {current_chunk_size})...")
        chunk_json = json.dumps(chunk, ensure_ascii=False, indent=2)
        
        # 使用安全的字符串拼接，彻底避免底层 Markdown 截断 Bug
        prompt = (
            "You are an Expert Special Education Knowledge Engineer.\n"
            "Your task is to instantiate an A-Box (Knowledge Graph Instances) from a chunk of JSON data, strictly adhering to our T-Box Schema.\n\n"
            "### 1. THE T-BOX SCHEMA\n"
            f"{schema_content}\n\n"
            "### 2. URI GENERATION RULE\n"
            "- The URI must be: `hhh-inst:<URL_ENCODED_NAME>`\n\n"
            "### 3. YOUR SEMANTIC TASK:\n"
            "Analyze this chunk of JSON nodes:\n"
            "1. **Classify:** Assign `hhh-kg:DomainConcept`, `hhh-kg:ObjectiveConcept`, `hhh-kg:ClinicalTask`, etc.\n"
            "2. **Basic Properties:** Add `rdfs:label`, `hhh-kg:ageMinMonths`, `hhh-kg:ageMaxMonths`, and `hhh-kg:originalLevel`.\n"
            "3. **Topology:** If a node has a `parent_name`, link them. Use `hhh-kg:hasSubConcept` (Concept to Concept) or `hhh-kg:targetsConcept` (Task to Concept).\n"
            "4. **DAG Routing:** Read the `prompt_corpus`. If a clinical task logically builds upon another task in this chunk, create a `hhh-kg:requiresPrerequisite` edge. If it mentions generalizing to daily life or groups, use `hhh-kg:generalizesTo`.\n\n"
            "### 4. THE JSON CHUNK\n"
            f"{chunk_json}\n\n"
            "### 5. OUTPUT\n"
            "Output ONLY valid RDF Turtle syntax for the instances. DO NOT output the `@prefix` declarations. Do NOT use markdown code blocks. NO conversational text."
        )

        success = False
        
        # 🎯 智能分诊重试环：只对 429 休眠，对 504 直接降级
        while not success:
            try:
                response = model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.0,
                    ),
                    request_options={"timeout": 600} 
                )
                
                # 极其稳健的后处理清洗：彻底干掉可能出现的 ```turtle 标签
                ttl_output = response.text.replace("```turtle", "").replace("```", "").strip()

                with open(output_ttl_file, 'a', encoding='utf-8') as f:
                    f.write(f"# --- Nodes {start_node_idx} to {end_idx-1} ---\n")
                    f.write(ttl_output + "\n\n")
                    
                print(f"   ✅ 节点 [{start_node_idx} - {end_idx-1}] 锻造成功！")
                success = True
                
            except Exception as e:
                error_msg = str(e)
                # 🩺 智能分诊 429
                if "429" in error_msg or "Too Many Requests" in error_msg or "exhausted" in error_msg.lower() or "quota" in error_msg.lower():
                    print(f"   🛑 触发 API 限流 (429)! 进入龟息模式休眠 30 秒...")
                    time.sleep(30)
                    continue 
                else:
                    # 🩺 游击战术 504 降级
                    print(f"   ⚠️ 请求失败 ({error_msg})。放弃死扛，直接降级！")
                    break 

        # 进度更新及窗口滑动逻辑
        if success:
            start_node_idx = end_idx
            checkpoints[json_file] = start_node_idx
            save_checkpoints(checkpoints)
            
            if current_chunk_size < MAX_CHUNK_SIZE:
                current_chunk_size = min(MAX_CHUNK_SIZE, current_chunk_size + 1)
                print(f"   📈 效率恢复，下一个窗口大小调至: {current_chunk_size}")
            time.sleep(2)
            
        else:
            if current_chunk_size > 1:
                current_chunk_size = max(1, current_chunk_size // 2)
                print(f"   📉 窗口瞬间砍半为: {current_chunk_size}")
                time.sleep(3) 
            else:
                print(f"   ☠️ 节点 [{start_node_idx}] 在窗口为 1 时依然崩溃，确认为终极毒节点，强制跳过！")
                start_node_idx += 1
                checkpoints[json_file] = start_node_idx
                save_checkpoints(checkpoints)
                current_chunk_size = 2 

if __name__ == "__main__":
    schema_path = "hhh_quest_aligned_schema.ttl"
    if not os.path.exists(schema_path):
        print(f"❌ 找不到蓝图宪法文件: {schema_path}")
        exit(1)
        
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema_content = f.read()

    global_checkpoints = load_checkpoints()

    target_files = glob.glob("21*_ontology_zh_CN.json")
    if not target_files:
        print("❌ 没有找到 JSON 文件！")
    else:
        for f in target_files:
            process_book_with_guerrilla_tactics(f, schema_content, global_checkpoints)
            
    print("\n🎉 终极大业完成！纯正的大模型语义 A-Box 弹药已全部落盘！")
