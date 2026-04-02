"""
数据清洗与知识图谱注入脚本
将生成的 JSON 扁平本体树转换为标准的 RDF Turtle (.ttl) 文件。

运行要求：
    pip install rdflib
"""

import json
import urllib.parse
from pathlib import Path

try:
    from rdflib import Graph, Namespace, Literal
    from rdflib.namespace import RDF, RDFS, XSD
except ImportError:
    print("Error: 缺少 'rdflib' 库。")
    print("请在运行前执行: pip install rdflib")
    exit(1)

def clean_uri(name: str) -> str:
    """
    将 name 编码为合法的 URI 后缀
    使用 urllib.parse.quote 处理中文和空格，保证生成合法的 URI。
    """
    if not name:
        return ""
    return urllib.parse.quote(name.strip())

def main():
    input_file = Path("scripts/data_extraction/21_heep_hong_language_ontology_zh_CN.json")
    output_file = Path("scripts/data_extraction/hhh_ontology.ttl")

    if not input_file.exists():
        print(f"Error: 找不到输入文件 {input_file}")
        # 如果指定名称不存在，尝试提示可能的文件名
        fallback_file = Path("scripts/data_extraction/21_heep_hong_language_ontology.json")
        if fallback_file.exists():
            print(f"提示: 发现同目录下存在 {fallback_file}，您可以修改脚本中的 input_file 路径。")
        return

    # 读取 JSON 数据
    with open(input_file, "r", encoding="utf-8") as f:
        nodes = json.load(f)

    # 初始化 Graph
    g = Graph()

    # 1. 命名空间定义
    HHH = Namespace("http://cuma.org/ontology/hhh#")
    g.bind("hhh", HHH)
    g.bind("rdf", RDF)
    g.bind("rdfs", RDFS)

    for node in nodes:
        name = node.get("name")
        if not name:
            continue

        # 2. URI 生成规则
        # 主语 (Subject): 节点的 name 对应的 URI
        subject_uri = HHH[clean_uri(name)]

        # 3. 属性映射规则 (Triple Mapping)
        # rdf:type 映射为 hhh:{level}
        level = node.get("level")
        if level:
            g.add((subject_uri, RDF.type, HHH[clean_uri(level)]))

        # rdfs:label 映射为 name 的 Literal
        g.add((subject_uri, RDFS.label, Literal(name)))

        # hhh:promptCorpus 映射
        prompt_corpus = node.get("prompt_corpus")
        if prompt_corpus:
            g.add((subject_uri, HHH.promptCorpus, Literal(prompt_corpus)))

        # hhh:ageMin / hhh:ageMax 映射
        # 兼容不同可能的月份字段命名
        age_min = node.get("age_min_months") if "age_min_months" in node else node.get("age_min")
        if age_min is not None:
            g.add((subject_uri, HHH.ageMin, Literal(int(age_min), datatype=XSD.integer)))

        age_max = node.get("age_max_months") if "age_max_months" in node else node.get("age_max")
        if age_max is not None:
            g.add((subject_uri, HHH.ageMax, Literal(int(age_max), datatype=XSD.integer)))

        # 4. 树状图谱拓扑关系构建
        parent_name = node.get("parent_name")
        if parent_name:
            parent_uri = HHH[clean_uri(parent_name)]
            # 当前节点 hhh:hasParent 父节点
            g.add((subject_uri, HHH.hasParent, parent_uri))
            # 父节点 hhh:hasChild 当前节点
            g.add((parent_uri, HHH.hasChild, subject_uri))

    # 5. 输出要求：序列化为 turtle 格式并保存
    # 确保目标目录存在
    output_file.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(destination=str(output_file), format="turtle")

    # 在控制台打印解析的节点总数，以及生成的 ttl 文件路径
    print(f"成功解析节点总数: {len(nodes)}")
    print(f"TTL 文件已生成并保存至: {output_file.absolute()}")

if __name__ == "__main__":
    main()
