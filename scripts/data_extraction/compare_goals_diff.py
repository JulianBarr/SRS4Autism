import json
import argparse
import re
from rdflib import Graph, Namespace, RDF, RDFS

HHS_ONT = Namespace("http://example.org/hhs/ontology#")

def parse_goal_description(desc):
    """解析 JSON 中的 goal description"""
    if not desc:
        return "", "", ""
    code = ""
    age = ""
    title = str(desc).strip()
    code_match = re.match(r'^\[(.*?)\]\s*(.*)', title)
    if code_match:
        code = code_match.group(1)
        title = code_match.group(2)
    age_match = re.search(r'/\s*([0-9\-至个岁月/ \.½]+)\s*$', title)
    if age_match:
        age = age_match.group(1).strip()
        title = title[:age_match.start()].strip()
    return code, title, age

def compare_diff(json_file, ttl_file):
    print(f"🔍 正在加载 TTL 图谱: {ttl_file}")
    g = Graph()
    g.parse(ttl_file, format="turtle")
    
    # 获取 TTL 中所有的 Goal Label 和 URI
    ttl_goals = {}
    for s in g.subjects(RDF.type, HHS_ONT.Goal):
        label = str(g.value(s, RDFS.label) or "")
        ttl_goals[str(s)] = label

    print(f"🔍 正在加载 JSON 数据: {json_file}")
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    json_goals = []
    # 提取 JSON 中所有的 Goal
    for sub in data.get("submodules", []):
        sub_title = sub.get("title", "")
        for obj in sub.get("objectives", []):
            for phasal in obj.get("phasal_objectives", []):
                p_title = phasal.get("title", "")
                for goal in phasal.get("goals", []):
                    raw_desc = goal.get("description", "")
                    code, core_title, age = parse_goal_description(raw_desc)
                    json_goals.append({
                        "raw_desc": raw_desc,
                        "core_title": core_title,
                        "age": age,
                        "path": f"{sub_title} -> {p_title}"
                    })

    print("\n" + "="*50)
    print("📊 差异对比报告 (DIFF REPORT)")
    print("="*50)
    print(f"📌 JSON 中提取到的 Goal 总数: {len(json_goals)}")
    print(f"📌 TTL 中实际生成的 Goal 节点数: {len(ttl_goals)}")
    print(f"📉 差异数 (丢失/合并): {len(json_goals) - len(ttl_goals)}\n")

    # 1. 检查 JSON 内部是否有完全重复的 core_title
    # 如果两个目标的 title 一模一样，在 TTL 里就会被当成同一个节点 (URI 碰撞)
    title_counts = {}
    for j_goal in json_goals:
        title = j_goal["core_title"]
        if title not in title_counts:
            title_counts[title] = []
        title_counts[title].append(j_goal)

    duplicates = {k: v for k, v in title_counts.items() if len(v) > 1}
    
    if duplicates:
        print("🚨 发现以下目标在 JSON 中出现了多次 (导致在 TTL 中被合并):")
        for title, items in duplicates.items():
            print(f"\n   🔹 核心标题: {title}")
            for i, item in enumerate(items):
                print(f"      [{i+1}] 原始描述: {item['raw_desc']}")
                print(f"          路径: {item['path']}")
    else:
        print("✅ JSON 中没有完全重复的核心标题。")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("json_file", help="输入的 JSON 文件")
    parser.add_argument("ttl_file", help="输入的 TTL 文件")
    args = parser.parse_args()
    
    compare_diff(args.json_file, args.ttl_file)
