import json
import os
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, XSD

def main():
    # 1. 零件清点：确保 5 个核心 JSON 文件都在目录下
    JSON_FILES = {
        "level1": "vbmapp_level1_normalized.json",
        "level2": "vbmapp_level2_normalized.json",
        "level3": "vbmapp_level3_normalized.json",
        "barriers": "vbmapp_barriers_cleaned.json",
        "transition": "vbmapp_transition_cleaned.json"
    }
    OUTPUT_TTL = "vbmapp_full_ontology.ttl"

    g = Graph()
    
    # 使用统一的 cuma.ai 命名空间，彻底告别旧系统
    VBMAPP_SCHEMA = Namespace("http://cuma.ai/schema/vbmapp/")
    VBMAPP_INST = Namespace("http://cuma.ai/instance/vbmapp/")
    
    g.bind("vbmapp-schema", VBMAPP_SCHEMA)
    g.bind("vbmapp-inst", VBMAPP_INST)
    g.bind("rdfs", RDFS)
    g.bind("xsd", XSD)

    def make_uri(node_id):
        # 统一规范：将 ID 中的短横线替换为下划线，确保 URI 兼容性
        safe_id = node_id.replace("-", "_")
        return VBMAPP_INST[safe_id]

    all_nodes = []
    for section, file_name in JSON_FILES.items():
        if os.path.exists(file_name):
            with open(file_name, 'r', encoding='utf-8') as f:
                nodes = json.load(f)
                all_nodes.extend(nodes)
                print(f"📦 已加载 {section}: {len(nodes)} 个节点")
        else:
            print(f"⚠️ 警告: 找不到文件 {file_name}，该部分将被跳过。")

    print(f"🚀 开始构建包含 {len(all_nodes)} 个节点的终极 VB-MAPP 知识图谱...")

    # --- 第一遍遍历：实例化所有节点 (A-Box) ---
    for node in all_nodes:
        node_uri = make_uri(node["id"])
        node_type = node.get("type")
        
        # 根据类型分流
        if node_type == "Domain":
            g.add((node_uri, RDF.type, VBMAPP_SCHEMA.Domain))
        elif node_type == "Barrier":
            g.add((node_uri, RDF.type, VBMAPP_SCHEMA.Barrier))
        elif node_type == "TransitionItem":
            g.add((node_uri, RDF.type, VBMAPP_SCHEMA.TransitionItem))
        else: # 默认为 Milestone
            g.add((node_uri, RDF.type, VBMAPP_SCHEMA.Milestone))
            
        # 基础属性映射
        if node.get("title"):
            g.add((node_uri, RDFS.label, Literal(node["title"], lang="en")))
            
        if node.get("domain"):
            g.add((node_uri, VBMAPP_SCHEMA.domainName, Literal(node["domain"], lang="en")))
            
        if node.get("level"):
            g.add((node_uri, VBMAPP_SCHEMA.level, Literal(int(node["level"]), datatype=XSD.integer)))
            
        if node.get("description"):
            g.add((node_uri, VBMAPP_SCHEMA.description, Literal(node["description"], lang="en")))
            
        if node.get("scoring_criteria"):
            g.add((node_uri, VBMAPP_SCHEMA.scoringCriteria, Literal(node["scoring_criteria"], lang="en")))

    # --- 第二遍遍历：织入 DAG 关系网 (The Engine) ---
    for node in all_nodes:
        parent_uri = make_uri(node["id"])
        
        # 1. 建立 Domain 到 Milestone 的包含关系
        for child_id in node.get("hasSubTask", []):
            child_uri = make_uri(child_id)
            g.add((parent_uri, VBMAPP_SCHEMA.hasSubTask, child_uri))
            
        # 2. 建立 Milestone 之间的前置依赖关系 (核心逻辑)
        for prereq_id in node.get("requiresPrerequisite", []):
            prereq_uri = make_uri(prereq_id)
            g.add((parent_uri, VBMAPP_SCHEMA.requiresPrerequisite, prereq_uri))

    # --- 保存最终成品 ---
    g.serialize(destination=OUTPUT_TTL, format="turtle")
    print(f"\n✨ 恭喜！VB-MAPP 全量数字化本体已生成: {OUTPUT_TTL}")
    print(f"📊 累计生成三元组 (Triples): {len(g)}")
    print("现在，你的 AI IEP 引擎已经拥有了一张完整的‘导航地图’。")

if __name__ == "__main__":
    main()
