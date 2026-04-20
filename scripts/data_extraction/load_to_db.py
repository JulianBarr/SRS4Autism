import pyoxigraph
import os
import shutil
from pathlib import Path

# 自动定位项目根目录 (假设此脚本在 scripts/data_extraction 下)
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent  # 退两级到 SRS4Autism 根目录

# 物理数据库存储路径
DB_PATH = PROJECT_ROOT / "data" / "knowledge_graph_store"

# 🌟 案发现场 A：旧核心资产目录 (内核与问卷)
LEGACY_KG_DIR = PROJECT_ROOT / "knowledge_graph"

# 🌟 案发现场 B：真正的语法库目录
CHINESE_GRAMMAR_DIR = PROJECT_ROOT / "tools" / "chinese_grammar"
ENGLISH_GRAMMAR_DIR = PROJECT_ROOT / "tools" / "english_grammar"

# 🌟 案发现场 C：今天的新成果目录 (CUMA对齐)
# 假设脚本在 SRS4Autism/scripts/data_extraction 下运行
NEW_CUMA_DIR = Path(".") 

def main():
    if DB_PATH.exists():
        print(f"🧹 正在清空旧图谱数据库残留数据: {DB_PATH}")
        shutil.rmtree(DB_PATH)

    print(f"🧱 正在创建纯净的物理图数据库: {DB_PATH}")
    store = pyoxigraph.Store(str(DB_PATH)) 

    # 🔪 跨多目录极简清单
    files_to_load = [
        # ==========================================
        # 1. 语言内核与问卷 (来自 knowledge_graph 目录)
        # ==========================================
        LEGACY_KG_DIR / "world_model_core.ttl",              # 23MB 纯净内核
        LEGACY_KG_DIR / "quest_full_with_vbmapp.ttl",        # Quest 桥接
        LEGACY_KG_DIR / "pep3_master.ttl",                   # PEP-3 量表
        LEGACY_KG_DIR / "survey_parent_full.ttl",                   # 家长问卷

        # ==========================================
        # 2. 真正的语法层 (来自 tools/ 下的专属目录)
        # ==========================================
        CHINESE_GRAMMAR_DIR / "grammar_layer.ttl",           # 🎯 中文语法层
        ENGLISH_GRAMMAR_DIR / "english_grammar_layer.ttl",   # 🎯 英文语法层

        # ==========================================
        # 3. 今天的全新基建与对齐 (当前执行目录)
        # ==========================================
        NEW_CUMA_DIR / "vbmapp_woven_ontology.ttl",         # 织好 DAG 的 VB-MAPP
        NEW_CUMA_DIR / "vbmapp_zh_supplement.ttl",          # 中文补充
        NEW_CUMA_DIR / "hhs_vbmapp_draft_alignment.ttl",    # 2112 条新连线

        # ==========================================
        # 4. 协康会 (HHS) 六神装 (当前执行目录)
        # ==========================================
        NEW_CUMA_DIR / "21_lang_debug_llm_enriched.ttl",
        NEW_CUMA_DIR / "22_cognition_debug_llm_enriched.ttl",
        NEW_CUMA_DIR / "23_self_care_debug_llm_enriched.ttl",
        NEW_CUMA_DIR / "24_social_emotions_debug_llm_enriched.ttl",
        NEW_CUMA_DIR / "25_gross_motor_debug_llm_enriched.ttl",
        NEW_CUMA_DIR / "26_fine_motor_debug_llm_enriched.ttl"
    ]

    print(f"📥 准备精准装载 {len(files_to_load)} 个图谱文件...")

    success_count = 0
    for file_path in files_to_load:
        if file_path.exists():
            print(f"  -> 正在猛烈灌入: {file_path.name}")
            with open(file_path, "rb") as f:
                store.bulk_load(f, pyoxigraph.RdfFormat.TURTLE)
            success_count += 1
        else:
            print(f"  ❌ 致命警告: 找不到文件 {file_path}，请检查路径！")

    if success_count < len(files_to_load):
        print("\n⚠️ 警告：有部分文件未能成功加载，请检查输出日志！")

    count = 0
    for _ in store.quads_for_pattern(None, None, None):
        count += 1
        
    print(f"\n✅ 物理装载彻底完成！跨 {success_count} 个文件融合成功，数据库当前容量: {count} 个三元组。")
    print(f"🚀 你的引擎终于达到完全体了，快去跑 learning_frontier_demo.py 吧！")

if __name__ == "__main__":
    main()
