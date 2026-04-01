import json

# 读取你刚跑完的数据
file_path = "21_heep_hong_language_ontology.json"

with open(file_path, "r", encoding="utf-8") as f:
    nodes = json.load(f)

print(f"📊 总节点数: {len(nodes)}")

# 1. 统计各个层级的数量分布
level_counts = {}
node_names = set()

for node in nodes:
    lvl = node.get("level", "Unknown")
    level_counts[lvl] = level_counts.get(lvl, 0) + 1
    node_names.add(node.get("name"))

print("\n📈 层级分布:")
for lvl in sorted(level_counts.keys()):
    print(f"  - {lvl}: {level_counts[lvl]} 个")

# 2. 查找孤儿节点 (断链检测)
orphans = []
for node in nodes:
    parent = node.get("parent_name")
    # 如果有 parent_name，但这个 parent 不在我们的所有节点名称池里
    if parent is not None and parent not in node_names:
        orphans.append(node)

print(f"\n⚠️ 发现孤儿节点: {len(orphans)} 个")

# 如果有孤儿，打印出来看看是哪些
if orphans:
    print("\n--- 孤儿节点详情 (可能是超时漏掉的父节点) ---")
    # 只打印前 5 个避免刷屏
    for orphan in orphans[:5]:
        print(f"节点: [{orphan['level']}] {orphan['name']}")
        print(f"丢失的父节点名: {orphan['parent_name']}\n")
    if len(orphans) > 5:
        print(f"... 以及其他 {len(orphans) - 5} 个。")
