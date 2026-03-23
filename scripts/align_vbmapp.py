import os
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS

# 1. 定义文件路径
# 请根据您的实际目录结构调整这里的路径
INPUT_TTL = "../knowledge_graph/quest_full.ttl"  # 修改为实际路径
OUTPUT_TTL = "../knowledge_graph/quest_full_with_vbmapp.ttl"

# 2. 定义命名空间 (Namespaces)
ECTA_INST = Namespace("http://ecta.ai/instance/")
ECTA_KG = Namespace("http://ecta.ai/schema/")
# 🌟 新增：专属的 VB-MAPP 命名空间
VBMAPP_INST = Namespace("http://ecta.ai/vbmapp/instance/")

def main():
    print("🚀 开始加载知识图谱...")
    g = Graph()
    
    # 绑定前缀，让输出的 TTL 文件更易读
    g.bind("ecta-inst", ECTA_INST)
    g.bind("ecta-kg", ECTA_KG)
    g.bind("vbmapp-inst", VBMAPP_INST)
    g.bind("rdfs", RDFS)

    if os.path.exists(INPUT_TTL):
        g.parse(INPUT_TTL, format="turtle")
        print(f"✅ 成功读取基础图谱，当前包含 {len(g)} 个三元组(Triples)。")
    else:
        print(f"❌ 找不到输入文件 {INPUT_TTL}，请检查路径！")
        return

    print("🧠 正在注入 VB-MAPP 本体与关联映射...")

    # ==========================================
    # 🌟 核心映射逻辑区
    # 这里我们以您刚才提到的 (3) 特征相同和不同（颜色、形状） 为例
    # ==========================================
    
    # 1. 在图谱中定义这个 VB-MAPP 节点本身（如果它还不存在）
    # VB019 代表: 视觉表现与配对 6-M (配对20个相同的物品或图片)
    vbmapp_node = VBMAPP_INST.VB019
    g.add((vbmapp_node, RDF.type, ECTA_KG.VBMAPP_Milestone))
    g.add((vbmapp_node, RDFS.label, Literal("视觉表现与配对 6-M：配对20个相同的物品或图片", lang="zh-CN")))
    g.add((vbmapp_node, ECTA_KG.domain, Literal("视觉表现与配对", lang="zh-CN")))
    g.add((vbmapp_node, ECTA_KG.level, Literal(2))) # 假设属于 Level 2

    # 2. 建立强关联 (Anchoring)
    # 找到原始的 task_1057，给它插上“必须先具备 VB019 能力”的属性
    target_task = ECTA_INST.task_1057
    g.add((target_task, ECTA_KG.requiresPrerequisite, vbmapp_node))

    # ==========================================
    # (您以后可以写个循环，读取 vbmapp_seeds.js 的 JSON 数据，
    # 在这里批量生成 g.add 逻辑)
    # ==========================================

    # 3. 保存为新的图谱文件
    g.serialize(destination=OUTPUT_TTL, format="turtle")
    print(f"🎉 注入完成！新的知识图谱已保存至: {OUTPUT_TTL}")
    print(f"📈 注入后包含 {len(g)} 个三元组(Triples)。")

if __name__ == "__main__":
    main()
