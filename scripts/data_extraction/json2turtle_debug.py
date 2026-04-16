import json
import argparse
import re
from rdflib import Graph, Literal, RDF, URIRef, Namespace
from rdflib.namespace import RDFS, XSD

# 定义命名空间
HHS_ONT = Namespace("http://example.org/hhs/ontology#")
HHS_RES = Namespace("http://example.org/hhs/resource/")

def clean_uri(text):
    if not text:
        return "unknown"
    clean_text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9_]', '_', text)
    clean_text = re.sub(r'_+', '_', clean_text).strip('_')
    return clean_text if clean_text else "resource"

def parse_goal_description(desc):
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

def ensure_list(data):
    """升级版防御机制：处理多行字符串的切割"""
    if not data:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, str):
        # 如果是带有换行符的长字符串 (例如 activity_suggestions)
        # 将其按行切割，并去掉空行
        return [line.strip() for line in data.split('\n') if line.strip()]
    return list(data)

def json_to_turtle(json_file, ttl_file):
    print(f"🔍 正在加载并分析 JSON 文件: {json_file}")
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    g = Graph()
    g.bind("hhs-ont", HHS_ONT)
    g.bind("hhs-res", HHS_RES)
    g.bind("rdfs", RDFS)

    stats = {
        "submodules": 0, "objectives": 0, "phasal_objectives": 0,
        "goals": 0, "activities_total": 0, "materials_total": 0
    }

    module_title = data.get("module") or "Unknown_Module"
    module_uri = HHS_RES[f"Module_{clean_uri(module_title)}"]
    g.add((module_uri, RDF.type, HHS_ONT.Module))
    g.add((module_uri, RDFS.label, Literal(module_title, lang="zh")))

    for sub in data.get("submodules", []):
        stats["submodules"] += 1
        sub_title = sub.get("title") or "Unknown_Submodule"
        sub_uri = HHS_RES[f"Submodule_{clean_uri(sub_title)}"]
        
        g.add((sub_uri, RDF.type, HHS_ONT.Submodule))
        g.add((sub_uri, RDFS.label, Literal(sub_title, lang="zh")))
        g.add((module_uri, HHS_ONT.hasSubmodule, sub_uri))

        for obj in sub.get("objectives", []):
            stats["objectives"] += 1
            obj_title = obj.get("title") or "Unknown_Objective"
            obj_uri = HHS_RES[f"Objective_{clean_uri(sub_title + '_' + obj_title)}"]
            
            g.add((obj_uri, RDF.type, HHS_ONT.Objective))
            g.add((obj_uri, RDFS.label, Literal(obj_title, lang="zh")))
            g.add((sub_uri, HHS_ONT.hasObjective, obj_uri))

            for phasal in obj.get("phasal_objectives", []):
                stats["phasal_objectives"] += 1
                p_index = phasal.get("index") or ""
                p_title = phasal.get("title") or "Unknown_Phasal"
                full_p_title = f"{p_index} {p_title}".strip()
                phasal_uri = HHS_RES[f"Phasal_{clean_uri(sub_title + '_' + full_p_title)}"]
                
                g.add((phasal_uri, RDF.type, HHS_ONT.PhasalObjective))
                g.add((phasal_uri, RDFS.label, Literal(full_p_title, lang="zh")))
                g.add((obj_uri, HHS_ONT.hasPhasalObjective, phasal_uri))

                for goal in phasal.get("goals", []):
                    stats["goals"] += 1
                    raw_desc = goal.get("description") or ""
                    code, core_title, age = parse_goal_description(raw_desc)
                    
                    goal_uri_str = clean_uri(f"{sub_title}_{p_title}_{code}_{core_title}")
                    goal_uri = HHS_RES[f"Goal_{goal_uri_str}"]
                    
                    g.add((goal_uri, RDF.type, HHS_ONT.Goal))
                    g.add((goal_uri, RDFS.label, Literal(core_title or "Untitled_Goal", lang="zh")))
                    g.add((phasal_uri, HHS_ONT.hasGoal, goal_uri))
                    
                    if code:
                        g.add((goal_uri, HHS_ONT.goalCode, Literal(code, datatype=XSD.string)))
                    if age:
                        g.add((goal_uri, HHS_ONT.ageGroup, Literal(age, lang="zh")))
                    
                    # 【核心修复】：兼容 activity_suggestions 和 activities，并且自动切割换行符
                    raw_activities = goal.get("activities") or goal.get("activity_suggestions") or goal.get("activity_suggestion")
                    activities = ensure_list(raw_activities)
                    stats["activities_total"] += len(activities)
                    for activity in activities:
                        g.add((goal_uri, HHS_ONT.hasActivity, Literal(activity, lang="zh")))
                        
                    materials = ensure_list(goal.get("materials"))
                    stats["materials_total"] += len(materials)
                    for material in materials:
                        g.add((goal_uri, HHS_ONT.hasMaterial, Literal(material, lang="zh")))
                        
                    for precaution in ensure_list(goal.get("precautions")):
                        g.add((goal_uri, HHS_ONT.hasPrecaution, Literal(precaution, lang="zh")))
                        
                    passing = goal.get("passing_criteria") or ""
                    if isinstance(passing, list):
                        passing = "\n".join(passing)
                    if passing:
                        g.add((goal_uri, HHS_ONT.hasPassingCriteria, Literal(passing, lang="zh")))

    print(f"⏳ 正在序列化并写入 {ttl_file} ...")
    g.serialize(destination=ttl_file, format='turtle')
    
    unique_goals_in_graph = len(list(g.subjects(RDF.type, HHS_ONT.Goal)))
    
    print("\n" + "="*40)
    print("📊 数据提取对账单 (DEBUG SUMMARY)")
    print("="*40)
    print(f"📝 发现 Submodules:        {stats['submodules']}")
    print(f"📝 发现 Objectives:        {stats['objectives']}")
    print(f"📝 发现 Phasal Objectives: {stats['phasal_objectives']}")
    print(f"📝 JSON 中提取的 Goals:    {stats['goals']}")
    print(f"🎯 图谱中唯一的 Goals URI: {unique_goals_in_graph}")
    print(f"🧩 提取出的活动(Activities): {stats['activities_total']} (Bug已修复！)")
    print(f"🛠️ 提取出的教具(Materials):  {stats['materials_total']}")
    print("="*40)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert HHS Enriched JSON to RDF Turtle (Fixed Activities)")
    parser.add_argument("json_file", help="输入的 JSON 文件")
    parser.add_argument("-o", "--output", default="hhs_graph.ttl", help="输出的 Turtle 文件")
    args = parser.parse_args()
    
    json_to_turtle(args.json_file, args.output)
