import os
import glob
from rdflib import Graph, Namespace

# 定义命名空间
HHH_KG = Namespace("http://cuma.org/schema/hhh/")
HHH_INST = Namespace("http://cuma.org/instance/hhh/")

def verify_kg_integrity(file_path):
    print(f"\n🔍 开始质检: {file_path}")
    g = Graph()
    
    # 1. 语法检查 (Syntax Error)
    try:
        g.parse(file_path, format="turtle")
        print("   ✅ 语法检查通过：无 Turtle 解析错误。")
    except Exception as e:
        print(f"   ❌ 语法致命错误: {e}")
        return

    # 2. 完整性检查 (Integrity)
    # 检查 A: 确保所有 targetConcept 指向的目标在这个图谱中存在
    dangling_concepts = g.query("""
        PREFIX hhh-kg: <http://cuma.org/schema/hhh/>
        SELECT ?task ?concept
        WHERE {
            ?task hhh-kg:targetsConcept ?concept .
            FILTER NOT EXISTS { ?concept ?p ?o }
        }
    """)
    if len(dangling_concepts) > 0:
        print(f"   ⚠️ 警告：发现 {len(dangling_concepts)} 个任务指向了不存在的 Concept！")
    else:
        print("   ✅ 引用完整性：所有 targetsConcept 指向明确。")

    # 检查 B: 确保所有前置依赖指向的目标存在
    dangling_prereqs = g.query("""
        PREFIX hhh-kg: <http://cuma.org/schema/hhh/>
        SELECT ?task ?prereq
        WHERE {
            ?task hhh-kg:requiresPrerequisite ?prereq .
            FILTER NOT EXISTS { ?prereq ?p ?o }
        }
    """)
    if len(dangling_prereqs) > 0:
        print(f"   ⚠️ 警告：发现 {len(dangling_prereqs)} 个任务的前置依赖不存在（可能是跨书本依赖或提取遗漏）！")
    else:
        print("   ✅ 依赖完整性：所有前置依赖任务明确。")

    print(f"   📊 统计: 本文件共包含 {len(g)} 个三元组 (Triples)。")

if __name__ == "__main__":
    abox_files = glob.glob("*_abox.ttl")
    if not abox_files:
        print("未找到任何 *_abox.ttl 文件。")
    for f in abox_files:
        verify_kg_integrity(f)
