import os
import glob
import numpy as np
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, RDFS
import google.generativeai as genai

# 配置 API
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# 命名空间
HHS_ONT = Namespace("http://example.org/hhs/ontology#")
CUMA_SCHEMA = Namespace("http://cuma.ai/schema/")
VBMAPP_INST = Namespace("http://cuma.ai/instance/vbmapp/")

def get_embedding(text):
    """调用 Gemini Embedding 模型获取文本的向量表示"""
    result = genai.embed_content(
        model="models/text-embedding-004", # 专门用于向量化的模型
        content=text,
        task_type="semantic_similarity"
    )
    return result['embedding']

def cosine_similarity(v1, v2):
    """计算两个向量的余弦相似度"""
    dot_product = np.dot(v1, v2)
    norm_v1 = np.linalg.norm(v1)
    norm_v2 = np.linalg.norm(v2)
    return dot_product / (norm_v1 * norm_v2)

def load_and_embed_vbmapp(vbmapp_ttl_path):
    """加载 VB-MAPP 并计算所有 Milestone 的向量"""
    print("🧠 正在向量化 VB-MAPP 里程碑...")
    g = Graph()
    g.parse(vbmapp_ttl_path, format="turtle")
    
    vbmapp_nodes = []
    milestone_uri = URIRef("http://cuma.ai/schema/vbmapp/Milestone")
    
    for s, p, o in g.triples((None, RDF.type, milestone_uri)):
        title = g.value(s, RDFS.label)
        desc = g.value(s, URIRef("http://cuma.ai/schema/vbmapp/description"))
        
        if title:
            # 将标题和描述合并，作为向量化的特征文本
            feature_text = f"{title}. {desc if desc else ''}"
            embedding = get_embedding(feature_text)
            
            vbmapp_nodes.append({
                "uri": s,
                "title": str(title),
                "embedding": embedding
            })
            
    print(f"✅ 完成 {len(vbmapp_nodes)} 个 VB-MAPP 节点的向量化。")
    return vbmapp_nodes

def load_hhs_goals(hhs_files):
    """加载所有 HHS 教学目标"""
    print("📂 正在提取协康会教学目标...")
    hhs_goals = []
    for file in hhs_files:
        g = Graph()
        g.parse(file, format="turtle")
        for s, p, o in g.triples((None, RDF.type, HHS_ONT.Goal)):
            label = g.value(s, RDFS.label)
            if label:
                hhs_goals.append({
                    "uri": s,
                    "text": str(label)
                })
    print(f"✅ 共提取 {len(hhs_goals)} 个协康会目标。")
    return hhs_goals

def main():
    VBMAPP_FILE = "vbmapp_full_ontology.ttl"
    HHS_FILES = glob.glob("??_*.ttl") # 读取所有 21_language.ttl, 22_cognition.ttl 等
    OUTPUT_TTL = "cuma_vector_links.ttl"
    
    # 1. 获取两边的特征向量
    vbmapp_nodes = load_and_embed_vbmapp(VBMAPP_FILE)
    hhs_goals = load_hhs_goals(HHS_FILES)
    
    out_graph = Graph()
    out_graph.bind("cuma-schema", CUMA_SCHEMA)
    
    print("🔍 开始进行高维向量空间相似度计算 (Vector Search)...")
    
    # 2. 遍历 HHS，计算与所有 VB-MAPP 的相似度，取 Top 2
    for i, goal in enumerate(hhs_goals):
        goal_embedding = get_embedding(goal["text"])
        
        # 计算当前目标与所有 VB-MAPP 节点的得分
        scored_nodes = []
        for v_node in vbmapp_nodes:
            score = cosine_similarity(goal_embedding, v_node["embedding"])
            scored_nodes.append((score, v_node))
            
        # 按分数降序排列，取 Top 2
        scored_nodes.sort(key=lambda x: x[0], reverse=True)
        top_matches = scored_nodes[:2]
        
        # 记录高质量的匹配 (可设置一个阈值，比如 > 0.65)
        for score, v_node in top_matches:
            if score > 0.65:  # 只有相似度够高才建立连接
                out_graph.add((goal["uri"], CUMA_SCHEMA.alignsWith, v_node["uri"]))
                out_graph.add((goal["uri"], CUMA_SCHEMA.matchScore, rdflib.Literal(float(score))))
        
        if (i+1) % 50 == 0:
            print(f"已处理 {i+1} / {len(hhs_goals)} 个目标...")

    out_graph.serialize(destination=OUTPUT_TTL, format="turtle")
    print(f"✨ 纯正的向量检索对齐完成！结果已保存至: {OUTPUT_TTL}")

if __name__ == "__main__":
    main()
