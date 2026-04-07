import pyoxigraph
import os

# 配置路径
DB_PATH = "../../data/knowledge_graph_store"
SCHEMA_FILE = "hhh_heep_hong_schema.ttl"
ABOX_FILE = "21_heep_hong_language_strict_abox.ttl"
NAMED_GRAPH_URI = "http://cuma.org/graph/heep-hong-language"

def main():
    print(f"\n📦 正在初始化/连接 Oxigraph 数据库: {DB_PATH}...")
    # 如果目录不存在，pyoxigraph 会自动创建
    store = pyoxigraph.Store(DB_PATH)

    # 1. 载入 T-Box 蓝图 (存入默认图 Default Graph)
    if os.path.exists(SCHEMA_FILE):
        print(f"📄 正在将本体蓝图 [{SCHEMA_FILE}] 注入默认空间...")
        with open(SCHEMA_FILE, "rb") as f:
            # Fix: Use format=pyoxigraph.RdfFormat.TURTLE instead of mime_type
            store.load(f, format=pyoxigraph.RdfFormat.TURTLE)
        print("   ✅ 蓝图注入成功！")
    else:
        print(f"   ❌ 致命错误：找不到本体蓝图文件 {SCHEMA_FILE}")
        return

    # 2. 载入 A-Box 数据 (存入命名图 Named Graph，实现物理隔离)
    if os.path.exists(ABOX_FILE):
        print(f"📚 正在将《语言》干预数据 [{ABOX_FILE}] 注入命名空间 <{NAMED_GRAPH_URI}>...")
        named_graph = pyoxigraph.NamedNode(NAMED_GRAPH_URI)
        with open(ABOX_FILE, "rb") as f:
            # Fix: Use format=pyoxigraph.RdfFormat.TURTLE instead of mime_type
            store.load(f, format=pyoxigraph.RdfFormat.TURTLE, base_iri=None, to_graph=named_graph)
        print("   ✅ 语言篇数据注入成功！")
    else:
        print(f"   ❌ 致命错误：找不到数据文件 {ABOX_FILE}")
        return

    # 3. 快速校验：统计库里到底有多少条三元组
    print("\n🔍 正在校验数据库状态...")
    count_query = "SELECT (COUNT(?s) AS ?count) WHERE { ?s ?p ?o }"
    result = list(store.query(count_query))
    count = result[0]['count'].value
    print(f"   📊 当前数据库总三元组 (Triples) 数量: {count}")
    
    print("\n🎉 入库大业完成！CUMA 系统的特教知识大脑已经就绪！")

if __name__ == "__main__":
    main()
