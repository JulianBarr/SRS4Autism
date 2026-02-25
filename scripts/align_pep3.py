import os
import rdflib
from rdflib import Graph, URIRef, Namespace

# 1. 动态获取绝对路径，防止在不同目录下运行报错
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
quest_path = os.path.join(BASE_DIR, "knowledge_graph", "quest_full.ttl")
pep3_path = os.path.join(BASE_DIR, "knowledge_graph", "pep3_master.ttl")

# 2. 初始化图谱，加载两个本体世界
g = Graph()
print("🔄 正在加载 ECTA 认知干预教案 (quest_full.ttl)...")
g.parse(quest_path, format="turtle")

print("🔄 正在加载 PEP-3 国际评估标准 (pep3_master.ttl)...")
g.parse(pep3_path, format="turtle")

# 3. 定义精确的命名空间 (Namespaces)
ECTA_INST = Namespace("http://ecta.ai/instance/")
ECTA_KG = Namespace("http://ecta.ai/schema/")
PEP3_INST = Namespace("http://ecta.ai/pep3/instance/") # 更新为最新的命名空间

# 4. 核心：执行自动化跨域对齐 (Alignment)
print("\n[引擎核心] 正在执行知识图谱跨域对齐 (ECTA Quests 🔗 PEP-3 Items)...")

# 规则 1：晏老师的“认识物件的特性/颜色配对” --> 对齐 --> PEP-3 第105、108题
g.add((ECTA_INST.obj_cog_032, ECTA_KG.alignsWithStandard, PEP3_INST.item_105))
g.add((ECTA_INST.obj_cog_032, ECTA_KG.alignsWithStandard, PEP3_INST.item_108))

# 规则 2：晏老师的“明白简单的数量概念” --> 对齐 --> PEP-3 第101、102题
g.add((ECTA_INST.obj_cog_044, ECTA_KG.alignsWithStandard, PEP3_INST.item_101))
g.add((ECTA_INST.obj_cog_044, ECTA_KG.alignsWithStandard, PEP3_INST.item_102))

print("✅ 对齐完成！内存中的知识图谱已打通。\n")

# 5. 见证奇迹：执行 SPARQL 图推演查询
sparql_query = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX ecta-kg: <http://ecta.ai/schema/>

SELECT ?macroLabel ?pep3Label
WHERE {
    # 找出一个机构宏观目标
    ?macroObj ecta-kg:alignsWithStandard ?pep3Item ;
              rdfs:label ?macroLabel .
              
    # 找出它对齐的 PEP-3 测试项的中文描述
    ?pep3Item rdfs:label ?pep3Label .
}
"""

print("================================================================")
print("🎯 知识图谱对齐查询结果 (可直接输出给前端 App 提示家长)：")
print("================================================================")
for row in g.query(sparql_query):
    macro_name = row.macroLabel.split(' ', 1)[-1] if ' ' in row.macroLabel else row.macroLabel
    pep3_standard = row.pep3Label
    
    print(f"🏥 机构教案: 《{macro_name}》")
    print(f"   => 📈 支撑国际标准: 攻克 [{pep3_standard}]")
    print("-" * 64)
