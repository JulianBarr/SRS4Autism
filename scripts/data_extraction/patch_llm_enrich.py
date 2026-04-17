import os
import json
import time
from pathlib import Path
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDFS, XSD
import google.generativeai as genai
from dotenv import load_dotenv

# 1. 初始化
env_path = Path(__file__).resolve().parent.parent / "gemini.env"
load_dotenv(env_path)
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# 🌟 关键：彻底关闭安全过滤器，防止“自理/洗澡/脱衣”等特教任务被误杀
from google.generativeai.types import HarmCategory, HarmBlockThreshold
safety_settings = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

model = genai.GenerativeModel('gemini-2.5-flash', safety_settings=safety_settings)

CUMA = Namespace("http://cuma.ai/schema/")

SYSTEM_PROMPT = """
你是一个特教数据提取专家。你需要从原始文本中提取 4 个字段：
1. cleanLabel: 剥离所有前缀和年龄信息的纯净动作描述。
2. module: 模块名称（如 认知、大肌肉 等）。如果没有填 null。
3. minAgeMonths: 最小适用年龄（换算成**个月**，整数）。
4. maxAgeMonths: 最大适用年龄（换算成**个月**，整数）。

请返回严格的 JSON 数组格式。
"""

def process_batch_with_llm(batch_texts):
    prompt = f"{SYSTEM_PROMPT}\n\n需要处理的文本 (JSON 数组):\n{json.dumps(batch_texts, ensure_ascii=False)}"
    try:
        response = model.generate_content(prompt)
        res_text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(res_text)
    except Exception as e:
        print(f"❌ 补漏请求依然失败: {e}")
        return None

def patch_ttl_file(file_path):
    g = Graph()
    g.parse(file_path, format="turtle")
    
    # 🌟 找出图谱中“有 label，但没有 cleanLabel” 的漏网之鱼
    missing_tasks = []
    for s, p, o in g.triples((None, RDFS.label, None)):
        if "hhs" in str(s).lower():
            if not list(g.objects(s, CUMA.cleanLabel)):
                missing_tasks.append((s, str(o)))
                
    if not missing_tasks:
        print(f"✅ {file_path.name} 完美无缺，无需补漏！")
        return
        
    print(f"🚑 发现 {len(missing_tasks)} 个漏网任务在 {file_path.name}，开始精准施救...")
    
    # 🌟 批次缩小到 5，防止一颗老鼠屎坏了一锅粥
    BATCH_SIZE = 5 
    
    for i in range(0, len(missing_tasks), BATCH_SIZE):
        batch = missing_tasks[i:i+BATCH_SIZE]
        batch_texts = [t[1] for t in batch]
        
        print(f"💉 正在修复漏洞批次 {i+1} 到 {min(i+BATCH_SIZE, len(missing_tasks))}...")
        results = process_batch_with_llm(batch_texts)
        
        if results and len(results) == len(batch):
            for (subject, _), res in zip(batch, results):
                g.add((subject, CUMA.cleanLabel, Literal(res.get("cleanLabel"), lang="zh")))
                if res.get("module"):
                    g.add((subject, CUMA.module, Literal(res.get("module"), lang="zh")))
                if res.get("minAgeMonths") is not None:
                    g.add((subject, CUMA.minAgeMonths, Literal(res.get("minAgeMonths"), datatype=XSD.integer)))
                if res.get("maxAgeMonths") is not None:
                    g.add((subject, CUMA.maxAgeMonths, Literal(res.get("maxAgeMonths"), datatype=XSD.integer)))
        else:
            print(f"⚠️ 补漏批次依然失败，跳过...")
            
        time.sleep(2)
        
    # 直接覆写原来的 _enriched 文件
    g.serialize(destination=file_path, format="turtle")
    print(f"🎉 补漏完成！已覆盖: {file_path.name}")

if __name__ == "__main__":
    data_dir = Path(".") 
    # 只读那些已经生成的 llm_enriched 文件
    enriched_files = list(data_dir.glob("*_llm_enriched.ttl"))
    
    for f in enriched_files:
        patch_ttl_file(f)
