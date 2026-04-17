import json
from pathlib import Path
from rdflib import Graph, Namespace, URIRef

# 命名空间
CUMA = Namespace("http://cuma.ai/schema/")
VBMAPP_INST = Namespace("http://cuma.ai/instance/vbmapp/")

def main():
    data_dir = Path(".")
    json_file = data_dir / "alignment_candidates.json"
    out_ttl = data_dir / "hhs_vbmapp_draft_alignment.ttl"
    
    if not json_file.exists():
        print("❌ 找不到 JSON 文件")
        return

    with open(json_file, "r", encoding="utf-8") as f:
        candidates = json.load(f)

    g = Graph()
    g.bind("cuma-schema", CUMA)
    g.bind("vbmapp-inst", VBMAPP_INST)
    
    count = 0
    for item in candidates:
        hhs_uri_str = item.get("hhs_task_uri")
        
        # 过滤掉不需要对齐的“文件夹/层级”节点
        if not hhs_uri_str or "Submodule" in hhs_uri_str or hhs_uri_str.endswith("认知") or hhs_uri_str.endswith("大肌肉"):
            continue
            
        top_matches = item.get("top_3_matches", [])
        if top_matches and len(top_matches) > 0:
            # 容错：防止大模型偶尔把 key 写成 "uri" 而不是 "vbmapp_uri"
            best_match_uri = top_matches[0].get("vbmapp_uri") or top_matches[0].get("uri")
            
            # 🛡️ 核心防爆盾：如果连糊弄出来的 URI 都没有，或者不是合法的 HTTP 链接，直接放弃这条
            if not best_match_uri or not str(best_match_uri).startswith("http"):
                continue
            
            hhs_node = URIRef(hhs_uri_str)
            vbmapp_node = URIRef(best_match_uri)
            
            # 建立对齐边
            g.add((hhs_node, CUMA.alignsWith, vbmapp_node))
            count += 1

    g.serialize(destination=out_ttl, format="turtle")
    print(f"✅ 成功生成 {count} 条粗略对齐连线！已保存至 {out_ttl.name}")

if __name__ == "__main__":
    main()
