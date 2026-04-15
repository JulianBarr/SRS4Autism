import json
import argparse
import re
from rdflib import Graph, Literal, RDF, URIRef, Namespace
from rdflib.namespace import RDFS, XSD

# 定义命名空间 (Namespaces)
HHS_ONT = Namespace("http://example.org/hhs/ontology#")
HHS_RES = Namespace("http://example.org/hhs/resource/")

def clean_uri(text):
    """将文本转换为极其安全的 IRI 字符串（仅保留汉字、字母、数字、下划线）"""
    if not text:
        return "unknown"
    
    # 【核心修复】：使用白名单正则，匹配所有非(汉字、字母、数字、下划线)的字符
    # \u4e00-\u9fa5 涵盖了绝大多数常用汉字
    clean_text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9_]', '_', text)
    
    # 合并多个连续的下划线并去除首尾下划线
    clean_text = re.sub(r'_+', '_', clean_text).strip('_')
    
    return clean_text if clean_text else "resource"

def parse_goal_description(desc):
    """提取编号和年龄段"""
    if not desc:
        return "", "", ""
        
    code = ""
    age = ""
    title = str(desc)

    code_match = re.match(r'^\[(.*?)\]\s*(.*)', title)
    if code_match:
        code = code_match.group(1)
        title = code_match.group(2)

    age_match = re.search(r'/\s*([0-9-至个岁月/ ]+)$', title)
    if age_match:
        age = age_match.group(1).strip()
        title = title[:age_match.start()].strip()

    return code, title, age

def ensure_list(data):
    """防御机制：防止单字符串被 for 循环拆解"""
    if not data:
        return []
    if isinstance(data, str):
        return [data]
    return list(data)

def json_to_turtle(json_file, ttl_file):
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    g = Graph()
    g.bind("hhs-ont", HHS_ONT)
    g.bind("hhs-res", HHS_RES)
    g.bind("rdfs", RDFS)

    # 1. 建立 Module 节点
    module_title = data.get("module") or "Unknown_Module"
    module_uri = HHS_RES[f"Module_{clean_uri(module_title)}"]
    g.add((module_uri, RDF.type, HHS_ONT.Module))
    g.add((module_uri, RDFS.label, Literal(module_title, lang="zh")))

    # 2. 遍历 Submodules
    for sub in data.get("submodules") or []:
        sub_title = sub.get("title") or "Unknown_Submodule"
        sub_uri = HHS_RES[f"Submodule_{clean_uri(sub_title)}"]
        
        g.add((sub_uri, RDF.type, HHS_ONT.Submodule))
        g.add((sub_uri, RDFS.label, Literal(sub_title, lang="zh")))
        g.add((module_uri, HHS_ONT.hasSubmodule, sub_uri))

        # 3. 遍历 Objectives
        for obj in sub.get("objectives") or []:
            obj_title = obj.get("title") or "Unknown_Objective"
            obj_uri = HHS_RES[f"Objective_{clean_uri(sub_title + '_' + obj_title)}"]
            
            g.add((obj_uri, RDF.type, HHS_ONT.Objective))
            g.add((obj_uri, RDFS.label, Literal(obj_title, lang="zh")))
            g.add((sub_uri, HHS_ONT.hasObjective, obj_uri))

            # 4. 遍历 Phasal Objectives
            for phasal in obj.get("phasal_objectives") or []:
                p_index = phasal.get("index") or ""
                p_title = phasal.get("title") or "Unknown_Phasal"
                full_p_title = f"{p_index} {p_title}".strip()
                phasal_uri = HHS_RES[f"Phasal_{clean_uri(sub_title + '_' + full_p_title)}"]
                
                g.add((phasal_uri, RDF.type, HHS_ONT.PhasalObjective))
                g.add((phasal_uri, RDFS.label, Literal(full_p_title, lang="zh")))
                g.add((obj_uri, HHS_ONT.hasPhasalObjective, phasal_uri))

                # 5. 遍历 Goals (叶子节点)
                for goal in phasal.get("goals") or []:
                    raw_desc = goal.get("description") or ""
                    code, core_title, age = parse_goal_description(raw_desc)
                    
                    # 生成唯一 Goal URI
                    goal_uri_str = clean_uri(f"{sub_title}_{p_title}_{code}_{core_title}")
                    goal_uri = HHS_RES[f"Goal_{goal_uri_str}"]
                    
                    g.add((goal_uri, RDF.type, HHS_ONT.Goal))
                    g.add((goal_uri, RDFS.label, Literal(core_title or "Untitled_Goal", lang="zh")))
                    g.add((phasal_uri, HHS_ONT.hasGoal, goal_uri))
                    
                    if code:
                        g.add((goal_uri, HHS_ONT.goalCode, Literal(code, datatype=XSD.string)))
                    if age:
                        g.add((goal_uri, HHS_ONT.ageGroup, Literal(age, lang="zh")))
                    
                    for activity in ensure_list(goal.get("activities")):
                        g.add((goal_uri, HHS_ONT.hasActivity, Literal(activity, lang="zh")))
                        
                    for material in ensure_list(goal.get("materials")):
                        g.add((goal_uri, HHS_ONT.hasMaterial, Literal(material, lang="zh")))
                        
                    for precaution in ensure_list(goal.get("precautions")):
                        g.add((goal_uri, HHS_ONT.hasPrecaution, Literal(precaution, lang="zh")))
                        
                    passing = goal.get("passing_criteria") or ""
                    if isinstance(passing, list):
                        passing = "\n".join(passing)
                    if passing:
                        g.add((goal_uri, HHS_ONT.hasPassingCriteria, Literal(passing, lang="zh")))

    # 导出为 Turtle 格式
    g.serialize(destination=ttl_file, format='turtle')
    print(f"🎉 知识图谱已生成: {ttl_file} (共包含 {len(g)} 个三元组)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert HHS Enriched A-Box JSON to RDF Turtle")
    parser.add_argument("json_file", help="输入的 Enriched A-Box JSON 文件")
    parser.add_argument("-o", "--output", default="hhs_graph.ttl", help="输出的 Turtle (.ttl) 文件")
    args = parser.parse_args()
    
    json_to_turtle(args.json_file, args.output)
