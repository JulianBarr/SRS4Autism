import os
import time
import json
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS
import google.generativeai as genai

# 使用你指定的性价比之王！
MODEL_NAME = 'gemini-2.5-flash'
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

VBMAPP_SCHEMA = Namespace("http://cuma.ai/schema/vbmapp/")
VBMAPP_INST = Namespace("http://cuma.ai/instance/vbmapp/")

def translate_batch(batch_nodes):
    """批量翻译，强制输出 JSON"""
    model = genai.GenerativeModel(MODEL_NAME)
    
    # 构造输入 JSON
    input_data = [{"uri": str(uri), "title": title, "desc": desc} for uri, title, desc in batch_nodes]
    
    prompt = f"""
    你是一名资深的 BCBA（行为分析师）。请将以下 VB-MAPP 的英文节点批量翻译为专业且易懂的中文。
    请注意特教术语：Tact(命名), Mand(要求), Intraverbal(交互式语言/对话), Echoic(仿编), VP-MTS(视觉感知与样本配对)。

    【输入数据】:
    {json.dumps(input_data, ensure_ascii=False, indent=2)}

    【输出要求】:
    请返回一个 JSON 数组，格式必须完全一致，包含 uri, zh_title, zh_desc：
    [
      {{"uri": "http://...", "zh_title": "中文标题", "zh_desc": "中文描述"}}
    ]
    """
    try:
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        return json.loads(response.text)
    except Exception as e:
        print(f"⚠️ 批处理翻译失败: {e}")
        return []

def main():
    print(f"🚀 启动极速批量翻译 (引擎: {MODEL_NAME})...")
    g = Graph()
    g.parse("vbmapp_full_ontology.ttl", format="turtle")

    out_g = Graph()
    out_g.bind("rdfs", RDFS)
    out_g.bind("vbmapp-schema", VBMAPP_SCHEMA)
    out_g.bind("vbmapp-inst", VBMAPP_INST)

    nodes_to_translate = []
    for type_uri in [VBMAPP_SCHEMA.Milestone, VBMAPP_SCHEMA.Barrier, VBMAPP_SCHEMA.TransitionItem]:
        for s, p, o in g.triples((None, RDF.type, type_uri)):
            title = str(g.value(s, RDFS.label) or "")
            desc = str(g.value(s, VBMAPP_SCHEMA.description) or "")
            if title:
                nodes_to_translate.append((s, title, desc))

    print(f"📦 发现 {len(nodes_to_translate)} 个待翻译节点。")

    # 批处理逻辑 (每批 30 个)
    batch_size = 30
    for i in range(0, len(nodes_to_translate), batch_size):
        batch = nodes_to_translate[i:i+batch_size]
        print(f"⏳ 正在翻译第 {i+1} 到 {min(i+batch_size, len(nodes_to_translate))} 个节点...")
        
        translated_results = translate_batch(batch)
        
        for result in translated_results:
            uri = URIRef(result["uri"])
            out_g.add((uri, RDFS.label, Literal(result["zh_title"], lang="zh")))
            out_g.add((uri, VBMAPP_SCHEMA.description, Literal(result["zh_desc"], lang="zh")))
            
        time.sleep(2) # 稍微休息一下防并发限制

    out_g.serialize(destination="vbmapp_zh_supplement.ttl", format="turtle")
    print("✅ 批量翻译完成！已生成 vbmapp_zh_supplement.ttl，请将其导入 Oxigraph！")

if __name__ == "__main__":
    main()
