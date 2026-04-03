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
# 听主公的，用视觉和逻辑最顶级的 3.1 预览版
model = genai.GenerativeModel('gemini-3.1-pro-preview')

CHECKPOINT_FILE = "abox_checkpoint.json"

def load_checkpoints():
    """加载断点记录"""
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_checkpoints(data):
    """实时保存断点记录"""
    with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def process_book_with_adaptive_window(json_file, schema_content, checkpoints):
    print(f"\n==================================================")
    print(f"📚 正在启动自适应装甲流水线: {json_file}")
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    output_ttl_file = json_file.replace("_ontology_zh_CN.json", "_abox.ttl")
    total_nodes = len(data)
    
    # 获取本书的断点进度 (以处理完的 Node 索引为准)
    start_node_idx = checkpoints.get(json_file, 0)

    # 只有在从零开始时，才清空并写入前缀
    if start_node_idx == 0:
        with open(output_ttl_file, 'w', encoding='utf-8') as f:
            f.write("@prefix hhh-kg: <http://cuma.org/schema/hhh/> .\n")
            f.write("@prefix hhh-inst: <http://cuma.org/instance/hhh/> .\n")
            f.write("@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n")
            f.write("@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n\n")
    else:
        print(f"   ♻️ 发现断点记录！已成功处理 {start_node_idx} 个节点，继续推进...")

    if start_node_idx >= total_nodes:
        print("   ✅ 这本书之前已全部锻造完毕，跳过。")
        return

    # 初始滑动窗口大小
    current_chunk_size = 10

    while start_node_idx < total_nodes:
        # 确保窗口不会越界
        end_idx = min(start_node_idx + current_chunk_size, total_nodes)
        chunk = data[start_node_idx:end_idx]
        
        print(f"   ⏳ 正在处理节点 [{start_node_idx} - {end_idx-1}] (本批 {len(chunk)} 个, 窗口大小: {current_chunk_size})...")
        chunk_json = json.dumps(chunk, ensure_ascii=False, indent=2)
        
        prompt = f"""
        You are an Expert Special Education Knowledge Engineer.
        Your task is to instantiate an A-Box (Knowledge Graph Instances) from a chunk of JSON data, strictly adhering to our T-Box Schema.

        ### 1. THE T-BOX SCHEMA (YOUR CONSTITUTION)
        ```turtle
        {schema_content}
        ```

        ### 2. URI GENERATION RULE (CRITICAL FOR CROSS-CHUNK LINKING)
        You must generate deterministic URIs for every node so different chunks can link together correctly.
        - The URI must be: `hhh-inst:<URL_ENCODED_NAME>`
        - Example: If name is "语言理解", the URI MUST BE `hhh-inst:%E8%AF%AD%E8%A8%80%E7%90%86%E8%A7%A3`

        ### 3. YOUR SEMANTIC TASK:
        Analyze this chunk of JSON nodes:
        1. **Classify:** Assign `hhh-kg:DomainConcept`, `hhh-kg:ObjectiveConcept`, `hhh-kg:ClinicalTask`, etc., based on the SEMANTIC MEANING of the node, not just blindly following L1-L6. 
        2. **Basic Properties:** Add `rdfs:label`, `hhh-kg:ageMinMonths`, `hhh-kg:ageMaxMonths`, and `hhh-kg:originalLevel`.
        3. **Topology:** If a node has a `parent_name`, link them. Use `hhh-kg:hasSubConcept` (Concept to Concept) or `hhh-kg:targetsConcept` (Task to Concept).
        4. **DAG Routing (The AI Magic):** Read the `prompt_corpus`. If a clinical task logically builds upon another task in this chunk, create a `hhh-kg:requiresPrerequisite` edge. If it mentions generalizing to daily life or groups, use `hhh-kg:generalizesTo`.

        ### 4. THE JSON CHUNK
        ```json
        {chunk_json}
        ```

        ### 5. OUTPUT
        Output ONLY valid RDF Turtle syntax for the instances. DO NOT output the `@prefix` declarations (they are already handled). Do NOT use markdown code blocks. NO conversational text.
        """

        max_retries = 3
        success = False

        for attempt in range(max_retries):
            try:
                response = model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.0, # 降温至0，减少注意力发散，极大降低超时概率
                    ),
                    request_options={"timeout": 600} 
                )
                
                ttl_output = response.text
                
                # 安全清理 markdown 护栏，避免截断代码
                ttl_output = ttl_output.strip()
                if ttl_output.startswith("```turtle"):
                    ttl_output = ttl_output[9:]
                elif ttl_output.startswith("```"):
                    ttl_output = ttl_output[3:]
                
                if ttl_output.endswith("```"):
                    ttl_output = ttl_output[:-3]

                # 追加写入文件 (Append Mode)
                with open(output_ttl_file, 'a', encoding='utf-8') as f:
                    f.write(f"# --- Nodes {start_node_idx} to {end_idx-1} ---\n")
                    f.write(ttl_output.strip() + "\n\n")
                    
                print(f"   ✅ 节点 [{start_node_idx} - {end_idx-1}] 锻造成功！")
                
                # 💥 关键点：成功后立即更新并保存断点
                start_node_idx = end_idx
                checkpoints[json_file] = start_node_idx
                save_checkpoints(checkpoints)
                success = True
                
                # 📈 奖励机制：如果是在降级后成功的，缓慢恢复窗口大小，提升效率
                if current_chunk_size < 10:
                    current_chunk_size = min(10, current_chunk_size + 2)
                    print(f"   📈 效率恢复，下一个窗口大小调至: {current_chunk_size}")

                # 冷却阀，防止 API 频率超限
                time.sleep(2)
                break # 成功则跳出重试循环
                
            except Exception as e:
                print(f"   ⚠️ 节点 [{start_node_idx} - {end_idx-1}] 尝试 {attempt + 1} 失败: {e}")
                if attempt < max_retries - 1:
                    sleep_time = 5 * (attempt + 1) # 指数退避: 5s, 10s...
                    print(f"   🔄 等待 {sleep_time} 秒后重试...")
                    time.sleep(sleep_time)

        # 🛑 核心自适应防御逻辑：如果 3 次尝试全部失败
        if not success:
            if current_chunk_size > 1:
                # 窗口减半，缩小排查范围
                current_chunk_size = max(1, current_chunk_size // 2)
                print(f"   📉 触发自适应降级！切片窗口缩小为: {current_chunk_size}")
            else:
                # 已经是 1 个节点了，依然失败，判定为无药可救的“毒节点”
                print(f"   ☠️ 节点 [{start_node_idx}] 确认为不可救药的毒节点，强制跳过！")
                start_node_idx += 1
                checkpoints[json_file] = start_node_idx
                save_checkpoints(checkpoints)
                current_chunk_size = 2 # 跳过毒节点后，稍微恢复点体力去测下一个节点

if __name__ == "__main__":
    schema_path = "hhh_quest_aligned_schema.ttl"
    if not os.path.exists(schema_path):
        print(f"❌ 找不到蓝图宪法文件: {schema_path}")
        exit(1)
        
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema_content = f.read()

    # 读取全局断点
    global_checkpoints = load_checkpoints()

    # 建议灰度测试：如果你想单跑一本，就把下面这行改成 ["23-self-care_ontology_zh_CN.json"]
    target_files = glob.glob("23*_ontology_zh_CN.json")
    if not target_files:
        print("❌ 没有找到 JSON 文件！")
    else:
        for f in target_files:
            process_book_with_adaptive_window(f, schema_content, global_checkpoints)
            
    print("\n🎉 终极大业完成！纯正的大模型语义 A-Box 弹药已全部落盘！")
