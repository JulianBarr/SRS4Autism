import os
import glob
import numpy as np
import time
import argparse
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS
import google.generativeai as genai

HHS_ONT = Namespace("http://example.org/hhs/ontology#")
CUMA_SCHEMA = Namespace("http://cuma.ai/schema/")
VBMAPP_SCHEMA = Namespace("http://cuma.ai/schema/vbmapp/")
VBMAPP_INST = Namespace("http://cuma.ai/instance/vbmapp/")

def get_embedding(text, model_name, retries=3):
    """调用 Embedding 模型，带自动重试防崩溃"""
    for attempt in range(retries):
        try:
            result = genai.embed_content(
                model=model_name,
                content=text,
                task_type="semantic_similarity"
            )
            return result['embedding']
        except Exception as e:
            print(f"⚠️ Embedding API 异常 (尝试 {attempt+1}/{retries}): {e}")
            time.sleep(5) # 等 5 秒重试
    return None

def cosine_similarity(v1, v2):
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

def load_and_embed_vbmapp(vbmapp_ttl_path, model_name):
    print(f"🧠 正在向量化 VB-MAPP: {vbmapp_ttl_path}")
    g = Graph()
    g.parse(vbmapp_ttl_path, format="turtle")
    
    vbmapp_nodes = []
    for s, p, o in g.triples((None, RDF.type, VBMAPP_SCHEMA.Milestone)):
        title = g.value(s, RDFS.label)
        desc = g.value(s, VBMAPP_SCHEMA.description)
        if title:
            text = f"{title}. {desc if desc else ''}"
            vec = get_embedding(text, model_name)
            if vec:
                vbmapp_nodes.append({"uri": s, "text": text, "vector": vec})
    print(f"✅ 成功向量化 {len(vbmapp_nodes)} 个 VB-MAPP 里程碑。")
    return vbmapp_nodes

def load_and_embed_hhs(hhs_files, model_name):
    print(f"📂 正在向量化 HHS 目标，共 {len(hhs_files)} 个文件...")
    hhs_nodes = []
    
    for file in hhs_files:
        print(f"  - 正在处理: {file}")
        g = Graph()
        g.parse(file, format="turtle")
        
        count = 0
        for s, p, o in g.triples((None, RDF.type, HHS_ONT.Goal)):
            title = g.value(s, RDFS.label)
            activities = [str(a) for a in g.objects(s, HHS_ONT.hasActivity)]
            act_text = " ".join(activities[:2]) 
            
            if title:
                text = f"目标: {title}. 活动: {act_text}"
                vec = get_embedding(text, model_name)
                if vec:
                    hhs_nodes.append({"uri": s, "text": text, "vector": vec})
                    count += 1
                time.sleep(0.05) # 极短休眠，防并发超载
        print(f"    提取了 {count} 个目标。")
    return hhs_nodes

def main():
    parser = argparse.ArgumentParser(description="高维向量语义对齐引擎")
    parser.add_argument("-v", "--vbmapp", required=True, help="VB-MAPP 的核心 TTL")
    parser.add_argument("-i", "--inputs", required=True, nargs='+', help="HHS TTL 文件列表")
    parser.add_argument("-o", "--output", default="cuma_full_alignment_links.ttl", help="输出的对齐链接")
    parser.add_argument("-t", "--threshold", type=float, default=0.65, help="最低相似度阈值")
    parser.add_argument("-m", "--model", default="models/text-embedding-004", help="指定的 Embedding 模型")
    
    args = parser.parse_args()

    genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

    vbmapp_nodes = load_and_embed_vbmapp(args.vbmapp, args.model)
    hhs_nodes = load_and_embed_hhs(args.inputs, args.model)
    
    out_graph = Graph()
    out_graph.bind("cuma-schema", CUMA_SCHEMA)
    out_graph.bind("vbmapp-inst", VBMAPP_INST)
    
    print(f"\n🔍 正在本地进行高维矩阵交叉计算 (阈值: {args.threshold})...")
    
    matches_found = 0
    for hhs in hhs_nodes:
        scored = [(cosine_similarity(hhs["vector"], vbm["vector"]), vbm["uri"]) for vbm in vbmapp_nodes]
        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best_vbmapp_uri = scored[0]
        
        if best_score > args.threshold:
            out_graph.add((hhs["uri"], CUMA_SCHEMA.alignsWith, best_vbmapp_uri))
            out_graph.add((hhs["uri"], CUMA_SCHEMA.matchScore, Literal(float(best_score))))
            matches_found += 1

    out_graph.serialize(destination=args.output, format="turtle")
    print("\n" + "="*50)
    print(f"🎉 语义对齐完成！成功建立 {matches_found} 条跨库关联。")
    print(f"💾 数据已保存至: {args.output}")
    print("="*50)

if __name__ == "__main__":
    main()
