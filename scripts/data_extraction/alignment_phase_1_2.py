import os
import json
import asyncio
from pathlib import Path
from rdflib import Graph, Namespace
from rdflib.namespace import RDF, RDFS, XSD
import google.generativeai as genai
from dotenv import load_dotenv
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# 1. 初始化 Gemini API
env_path = Path(__file__).resolve().parent.parent.parent / "gemini.env" 
load_dotenv(env_path)
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# 🌟 关键：彻底关闭安全过滤器，保护特教自理任务不被误杀
safety_settings = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

# 🌟 使用 Flash Lite Preview 模型探路
model = genai.GenerativeModel('gemini-3.1-flash-lite-preview', safety_settings=safety_settings)

# 2. 定义图谱命名空间
CUMA = Namespace("http://cuma.ai/schema/")
VBMAPP_SCHEMA = Namespace("http://cuma.ai/schema/vbmapp/")
VBMAPP_INST = Namespace("http://cuma.ai/instance/vbmapp/")

# 3. 核心 Prompt 设计
SYSTEM_PROMPT = """
你是一名资深的应用行为分析师 (BCBA) 和特殊教育专家。
你的任务是将一系列“协康会(HHS)的具体干预任务”对齐到“VB-MAPP 的能力评估里程碑”上。

下面是经过年龄初步过滤后的【VB-MAPP 候选池】(JSON 格式):
{vbmapp_pool_json}

请仔细阅读上述 VB-MAPP 里程碑的含义和要求。
现在，我将给你一批【HHS 任务】。对于每一个 HHS 任务，请仔细思考它的核心动机(MO)和前置要求，并从上述候选池中选出**最有可能作为其直接评估目标**的 TOP 3 个 VB-MAPP 里程碑。

返回格式必须是严格的 JSON 数组，顺序与输入的 HHS 任务一致：
[
  {
    "hhs_task_uri": "http://...",
    "hhs_clean_label": "任务名称",
    "top_3_matches": [
      {"vbmapp_uri": "http://...", "reason": "一句话解释为什么匹配，结合 ABA 理论"}
    ]
  }
]
"""

def load_graph(file_paths):
    g = Graph()
    for fp in file_paths:
        if fp.exists():
            g.parse(fp, format="turtle")
            print(f"📥 成功加载: {fp.name}")
        else:
            print(f"⚠️ 文件未找到，跳过: {fp.name}")
    return g

def extract_vbmapp_pool(g, min_age_filter):
    """提取 VB-MAPP 候选池，根据 HHS 任务的年龄进行粗筛"""
    pool = []
    for ms in g.subjects(RDF.type, VBMAPP_SCHEMA.Milestone):
        level = g.value(ms, VBMAPP_SCHEMA.level)
        label = g.value(ms, RDFS.label)
        desc = g.value(ms, VBMAPP_SCHEMA.description)
        domain = g.value(ms, VBMAPP_SCHEMA.domainName)
        
        # Phase 1: 物理硬过滤
        if level:
            level_num = int(level)
            if min_age_filter > 48 and level_num == 1:
                continue 
                
        pool.append({
            "uri": str(ms),
            "label": str(label) if label else "",
            "description": str(desc) if desc else "",
            "level": str(level) if level else "",
            "domain": str(domain) if domain else ""
        })
    return pool

def get_hhs_tasks(g):
    """提取需要对齐的 HHS 任务"""
    tasks = []
    for s, p, o in g.triples((None, CUMA.cleanLabel, None)):
        min_age = g.value(s, CUMA.minAgeMonths)
        module = g.value(s, CUMA.module)
        tasks.append({
            "uri": str(s),
            "clean_label": str(o),
            "min_age": int(min_age) if min_age else 0,
            "module": str(module) if module else ""
        })
    return tasks

async def call_llm_batch(batch_tasks, vbmapp_pool):
    """异步调用 Gemini 进行对齐"""
    prompt = SYSTEM_PROMPT.replace("{vbmapp_pool_json}", json.dumps(vbmapp_pool, ensure_ascii=False, indent=2))
    prompt += f"\n\n【HHS 任务批次】:\n{json.dumps(batch_tasks, ensure_ascii=False, indent=2)}"
    
    try:
        response = await model.generate_content_async(prompt)
        res_text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(res_text)
    except Exception as e:
        print(f"❌ API 失败或 JSON 解析错误: {e}")
        return None

async def main():
    data_dir = Path(".")
    out_file = data_dir / "alignment_candidates.json"
    
    print("⏳ 正在搜集图谱文件...")
    vbmapp_file = data_dir / "vbmapp_woven_ontology.ttl"
    hhs_files = list(data_dir.glob("*_llm_enriched.ttl"))
    
    if not vbmapp_file.exists():
        print("❌ 找不到 vbmapp_woven_ontology.ttl，请检查路径！")
        return
        
    if not hhs_files:
        print("❌ 找不到任何 *_llm_enriched.ttl 文件！")
        return

    g = load_graph([vbmapp_file] + hhs_files)
    hhs_tasks = get_hhs_tasks(g)
    
    # 🌟 断点续传核心逻辑 🌟
    all_results = []
    processed_uris = set()
    
    if out_file.exists():
        try:
            with open(out_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content: # 确保文件不是完全空的
                    all_results = json.loads(content)
                    processed_uris = {res.get("hhs_task_uri") for res in all_results if "hhs_task_uri" in res}
            print(f"🔄 发现断点存档！已跳过 {len(processed_uris)} 条已处理的任务。")
        except json.JSONDecodeError:
            print("⚠️ 存档文件 JSON 损坏，将从头开始覆盖...")

    # 过滤出还没跑过的任务
    pending_tasks = [t for t in hhs_tasks if t["uri"] not in processed_uris]
    
    if not pending_tasks:
        print("✅ 所有任务都已对齐完毕，无需再跑！")
        return
        
    print(f"📦 剩余待处理任务: {len(pending_tasks)} 个。")
    
    # 🌟 因为是 Lite 模型，Batch Size 稍微放大到 20 提速
    BATCH_SIZE = 20 
    
    for i in range(0, len(pending_tasks), BATCH_SIZE):
        batch = pending_tasks[i:i+BATCH_SIZE]
        
        avg_age = sum(t["min_age"] for t in batch) / len(batch)
        vbmapp_pool = extract_vbmapp_pool(g, min_age_filter=avg_age)
        
        current_batch_num = i // BATCH_SIZE + 1
        total_batches = (len(pending_tasks) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"🚀 正在处理剩余批次 {current_batch_num}/{total_batches} (当前候选池: {len(vbmapp_pool)} 个)...")
        
        results = await call_llm_batch(batch, vbmapp_pool)
        
        if results:
            all_results.extend(results)
            # 🌟 每跑完一批，立刻覆写存档
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(all_results, f, ensure_ascii=False, indent=2)
            print(f"💾 批次 {current_batch_num} 已自动存档。")
            
        # 🌟 休眠 2 秒，Lite 模型限制相对较松
        await asyncio.sleep(2) 
        
    print(f"✅ 大功告成！所有任务的对齐候选结果已全部保存至: {out_file}")

if __name__ == "__main__":
    asyncio.run(main())
