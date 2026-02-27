import os
import json
import glob
from rdflib import Graph, Literal, Namespace
from rdflib.namespace import RDF, RDFS

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEST_TTL_PATH = os.path.join(BASE_DIR, "knowledge_graph", "quest_full.ttl")
JSON_DIR = os.path.join(BASE_DIR, "data_prep", "extracted_json")

ECTA_KG = Namespace("http://ecta.ai/schema/")

def main():
    if not os.path.exists(QUEST_TTL_PATH):
        print(f"❌ 找不到图谱: {QUEST_TTL_PATH}")
        return

    g = Graph()
    g.parse(QUEST_TTL_PATH, format="turtle")
    g.bind("ecta-kg", ECTA_KG)

    # 1. 建立 图谱中节点名称 -> 节点URI 的快速映射字典
    label_to_uri = {}
    for s, p, o in g.triples((None, RDFS.label, None)):
        label_to_uri[str(o).strip()] = s

    # 2. 读取所有的临时 JSON 文件
    json_files = glob.glob(os.path.join(JSON_DIR, "*.json"))
    updated_count = 0
    
    print(f"🚀 开始扫描 {len(json_files)} 个 JSON 文件并注入富文本内容...")

    for filepath in json_files:
        with open(filepath, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                # 兼容不同的 JSON 格式（有些是直接的列表，有些包装在字典里）
                if isinstance(data, dict):
                    data = data.get("quests", []) or data.get("tasks", []) or [data]
            except json.JSONDecodeError:
                continue

        for quest in data:
            q_name = quest.get("quest_name", "").strip()
            if not q_name:
                continue

            # 3. 在图谱中寻找匹配的节点 (精确匹配 -> 包含匹配)
            target_uri = label_to_uri.get(q_name)
            if not target_uri:
                for lbl, uri in label_to_uri.items():
                    if q_name in lbl or lbl in q_name:
                        target_uri = uri
                        break

            # 4. 如果找到了节点，把它的血肉全挂上去！
            if target_uri:
                # 注入教具 (可能有多个)
                materials = quest.get("materials", [])
                if isinstance(materials, str):
                    materials = [materials]
                
                # 先清空旧的（防重复）
                g.remove((target_uri, ECTA_KG.suggestedMaterials, None))
                for mat in materials:
                    g.add((target_uri, ECTA_KG.suggestedMaterials, Literal(mat)))

                # 注入教学步骤
                steps = quest.get("teaching_steps", "")
                if steps:
                    g.remove((target_uri, ECTA_KG.teachingSteps, None))
                    g.add((target_uri, ECTA_KG.teachingSteps, Literal(steps)))

                # 注入集体课泛化
                gc_gen = quest.get("group_class_generalization", "")
                if gc_gen:
                    g.remove((target_uri, ECTA_KG.groupClassGeneralization, None))
                    g.add((target_uri, ECTA_KG.groupClassGeneralization, Literal(gc_gen)))

                # 注入家庭泛化
                home_gen = quest.get("home_generalization", "")
                if home_gen:
                    g.remove((target_uri, ECTA_KG.homeGeneralization, None))
                    g.add((target_uri, ECTA_KG.homeGeneralization, Literal(home_gen)))

                updated_count += 1
                print(f"✅ 已注入: 《{q_name}》")

    g.serialize(destination=QUEST_TTL_PATH, format="turtle")
    print(f"\n🎉 注入完成！共成功把 {updated_count} 个任务的【教具、教学步骤、泛化建议】写回了核心图谱。")

if __name__ == "__main__":
    main()
