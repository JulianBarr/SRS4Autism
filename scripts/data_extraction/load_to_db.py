import pyoxigraph
import os

# 已经根据你的配置，指向了上两级的持久化目录
DB_PATH = "../../knowledge_graph_data"  

def main():
    print(f"🧱 正在连接物理图数据库: {DB_PATH}")
    store = pyoxigraph.Store(DB_PATH) 

    # 毫无保留地列出所有核心文件和 6 本 HHS 秘籍
    all_files = [
        # 1. 核心底座与对齐
        "vbmapp_full_ontology.ttl",
        "vbmapp_zh_supplement.ttl",
        "cuma_full_alignment_links.ttl",
        
        # 2. 协康会六神装 (HHS)
        "21_lang_debug.ttl",
        "22_cognition_debug.ttl",
        "23_self_care_debug.ttl",
        "24_social_emotions_debug.ttl",
        "25_gross_motor_debug.ttl",
        "26_fine_motor_debug.ttl"
    ]

    print(f"📥 准备精准装载 {len(all_files)} 个图谱文件...")

    for file_name in all_files:
        if os.path.exists(file_name):
            print(f"  -> 正在猛烈灌入: {file_name}")
            # 【核心修复】：必须以二进制读取模式 (rb) 打开文件流
            # 同时使用 pyoxigraph.RdfFormat.TURTLE 解决弃用警告
            with open(file_name, "rb") as f:
                store.bulk_load(f, pyoxigraph.RdfFormat.TURTLE)
        else:
            print(f"  ❌ 致命警告: 找不到文件 {file_name}，请检查路径！")

    # 验证装载结果
    count = 0
    for _ in store.quads_for_pattern(None, None, None):
        count += 1
        
    print(f"\n✅ 物理装载彻底完成！数据库当前容量: {count} 个三元组。")
    print(f"🚀 现在你可以把 {DB_PATH} 目录交给 Next.js 了！")

if __name__ == "__main__":
    main()
