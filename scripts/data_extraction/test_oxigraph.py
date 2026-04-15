import pyoxigraph

store = pyoxigraph.Store()

print("⏳ 正在尝试加载图谱至 Oxigraph...")
try:
    # 尝试解析并加载 Turtle 文件
    store.load(open("21_language.ttl", "rb"), "text/turtle")
    print(f"✅ 成功！图谱加载无任何 Syntax Error。")
    print(f"📊 数据库当前包含 {len(store)} 个三元组。")
except Exception as e:
    print(f"❌ 解析失败，存在语法错误: {e}")
