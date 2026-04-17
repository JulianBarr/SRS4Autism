import os
import json
import time
from pathlib import Path
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDFS, XSD
import google.generativeai as genai
from dotenv import load_dotenv

# 1. 初始化 Gemini API
# 假设你的根目录有个 gemini.env
env_path = Path(__file__).resolve().parent.parent / "gemini.env"
load_dotenv(env_path)
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# 使用 Flash 模型，便宜且速度极快
model = genai.GenerativeModel('gemini-2.5-flash')

# 2. 定义图谱命名空间
CUMA = Namespace("http://cuma.ai/schema/")
HHS_INST = Namespace("http://cuma.ai/instance/hhs/")

# 3. 大模型清洗 Prompt
SYSTEM_PROMPT = """
你是一个特教数据提取专家。我会给你一批协康会 (HHS) 任务的原始文本。
这些文本通常包含：任务序号、任务描述、年龄段、模块等（格式非常混乱）。

你需要从中提取以下 4 个字段：
1. cleanLabel: 剥离所有前缀（如 A., (3)）、后缀（如 / 1-2岁）和年龄信息的纯净动作描述。
2. module: 任务属于哪个模块（如 认知、大肌肉、小肌肉、社交与情绪 等）。如果没有，填 null。
3. minAgeMonths: 最小适用年龄（换算成**个月**，必须是整数）。如果是 "1-2岁"，则是 12。如果是 "6-7个月"，则是 6。如果是 "通用"，填 0。
4. maxAgeMonths: 最大适用年龄（换算成**个月**，必须是整数）。如果是 "1-2岁"，则是 24。如果是 "通用"，填 72。

请返回严格的 JSON 数组格式，顺序与输入完全一致。
示例输入: ["A. 计算 1-10 以内加数 / 5-6 岁 | 模块: 认知 | 适用年龄: 通用", "持续用掌心抓握物件 | 模块: 小肌肉 | 适用年龄: 6-7 个月"]
示例输出: 
[
  {"cleanLabel": "计算 1-10 以内加数", "module": "认知", "minAgeMonths": 60, "maxAgeMonths": 72},
  {"cleanLabel": "持续用掌心抓握物件", "module": "小肌肉", "minAgeMonths": 6, "maxAgeMonths": 7}
]
"""

def process_batch_with_llm(batch_texts):
    """将一批文本发送给 LLM 进行结构化提取"""
    prompt = f"{SYSTEM_PROMPT}\n\n需要处理的文本 (JSON 数组):\n{json.dumps(batch_texts, ensure_ascii=False)}"
    
    try:
        response = model.generate_content(prompt)
        # 简单清理可能包含的 markdown json 标记
        res_text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(res_text)
    except Exception as e:
        print(f"❌ LLM 请求失败: {e}")
        return None

def process_ttl_file(file_path, output_path):
    g = Graph()
    g.parse(file_path, format="turtle")
    
    # 找出所有包含 rdfs:label 的节点（这部分你根据自己实际图谱结构调整）
    tasks = []
    for s, p, o in g.triples((None, RDFS.label, None)):
        if "hhs" in str(s).lower(): # 仅处理 HHS 节点
            tasks.append((s, str(o)))
            
    print(f"📦 找到 {len(tasks)} 个任务在 {file_path.name}")
    
    BATCH_SIZE = 20 # 每次让 LLM 处理 20 条，省钱又不会超 Token
    
    for i in range(0, len(tasks), BATCH_SIZE):
        batch = tasks[i:i+BATCH_SIZE]
        batch_texts = [t[1] for t in batch]
        
        print(f"🚀 正在呼叫 Gemini 处理第 {i+1} 到 {min(i+BATCH_SIZE, len(tasks))} 条...")
        results = process_batch_with_llm(batch_texts)
        
        if results and len(results) == len(batch):
            for (subject, _), res in zip(batch, results):
                # 写入清洗后的数据
                g.add((subject, CUMA.cleanLabel, Literal(res.get("cleanLabel"), lang="zh")))
                if res.get("module"):
                    g.add((subject, CUMA.module, Literal(res.get("module"), lang="zh")))
                if res.get("minAgeMonths") is not None:
                    g.add((subject, CUMA.minAgeMonths, Literal(res.get("minAgeMonths"), datatype=XSD.integer)))
                if res.get("maxAgeMonths") is not None:
                    g.add((subject, CUMA.maxAgeMonths, Literal(res.get("maxAgeMonths"), datatype=XSD.integer)))
        else:
            print(f"⚠️ 批次处理结果数量不匹配，跳过...")
            
        time.sleep(2) # 稍微限流，防止 API 报错
        
    g.serialize(destination=output_path, format="turtle")
    print(f"✅ 富化完成！已保存至: {output_path}")

if __name__ == "__main__":
    # 替换为你实际存放 HHS TTL 的目录
    data_dir = Path("./") 
    files = ["21_lang_debug.ttl", "22_cognition_debug.ttl", "23_self_care_debug.ttl", 
             "24_social_emotions_debug.ttl", "25_gross_motor_debug.ttl", "26_fine_motor_debug.ttl"]
    
    for f in files:
        in_file = data_dir / f
        out_file = data_dir / f.replace(".ttl", "_llm_enriched.ttl")
        if in_file.exists():
            process_ttl_file(in_file, out_file)
