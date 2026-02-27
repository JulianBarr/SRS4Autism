import os
import time
import google.generativeai as genai
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS

# ==========================================
# 1. API 与环境配置
# ==========================================
os.environ["HTTP_PROXY"] = "socks5://127.0.0.1:49682"
os.environ["HTTPS_PROXY"] = "socks5://127.0.0.1:49682"

api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=api_key)
# 使用极速且免费的 Flash 模型
model = genai.GenerativeModel('gemini-2.5-flash')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEST_TTL_PATH = os.path.join(BASE_DIR, "knowledge_graph", "quest_full.ttl")

ECTA_KG = Namespace("http://ecta.ai/schema/")

# ==========================================
# 2. 从您的照片提炼的目录大纲 (TOC Context)
# ==========================================
TOC_CONTEXT = """
这是孤独症儿童干预手册的目录（包含年龄段映射关系）：

【3-12个月】认知：控制身体、操控物件、物件存在概念；语言：发声；小肌肉：执笔准备；模仿：简单操弄。
【1-2岁】认知：视觉听觉辨别、常用物件名称功用、简单因果、空间位置；语言：模仿单词；小肌肉：执笔、拾放、玩具操作、拼砌、柱条插放；大肌肉：平衡、抛接、上下楼梯、推拉；模仿：简单动作。
【2-3岁】认知：专注力、符号化、分类概念、事情先后次序、数量概念；语言：不同词汇、2-3个词短句、使用问句；小肌肉：串连技能（如穿珠子）、写画、拼砌；大肌肉：球类、跳跃；模仿：连串动作。
【3-4岁】认知：身体感觉、物件特性、表达物件用途、抽象分类、数字意义、比较概念（大小长短粗细）；语言：3个词以上句子、疑问词、代名词；小肌肉：写画、剪刀操作；大肌肉：摇荡；模仿：精细身体动作。
【4-5岁】认知：复杂辨别、抽象属性、相似共同之处、数字与数量、相对概念；语言：复杂句子表达；小肌肉：折纸、积木堆砌、图工；模仿：复杂连串先后次序动作。
【5-6岁】认知：多方面属性、符号化阅读、因果推理、简单运算、道德观念；语言：抽象词汇；小肌肉：剪刀、写画。
"""

def guess_age_bracket(macro_label: str) -> str:
    prompt = f"""
    {TOC_CONTEXT}
    
    任务宏观目标名称：“{macro_label}”
    请根据上述目录大纲，推断该任务最可能属于哪个年龄段。
    严格只返回以下选项之一（不要包含任何其他废话）：
    '3-12个月', '1-2岁', '2-3岁', '3-4岁', '4-5岁', '5-6岁'。
    如果实在无法匹配，返回 '全年龄段'。
    """
    try:
        response = model.generate_content(prompt)
        res = response.text.strip().replace("'", "").replace('"', "")
        valid = ['3-12个月', '1-2岁', '2-3岁', '3-4岁', '4-5岁', '5-6岁', '全年龄段']
        return res if res in valid else '全年龄段'
    except Exception as e:
        print(f"API 请求失败: {e}")
        return "全年龄段"

def main():
    if not os.path.exists(QUEST_TTL_PATH):
        print(f"❌ 找不到图谱: {QUEST_TTL_PATH}")
        return

    g = Graph()
    g.parse(QUEST_TTL_PATH, format="turtle")
    g.bind("ecta-kg", ECTA_KG)
    
    # 查找所有 MacroObjective
    macros = list(g.subjects(RDF.type, ECTA_KG.MacroObjective))
    updated_count = 0
    
    print(f"🚀 开始扫描 {len(macros)} 个宏观目标，寻找缺失的年龄段...")

    for macro_uri in macros:
        # 检查是否已经有年龄段
        existing_age = list(g.objects(macro_uri, ECTA_KG.recommendedAgeBracket))
        if not existing_age:
            label = list(g.objects(macro_uri, RDFS.label))
            if label:
                macro_name = str(label[0])
                print(f"🔍 正在推断: 《{macro_name}》 ...", end=" ")
                
                # 呼叫 Gemini 推断年龄
                guessed_age = guess_age_bracket(macro_name)
                print(f"🎯 结果: {guessed_age}")
                
                # 写入图谱
                g.add((macro_uri, ECTA_KG.recommendedAgeBracket, Literal(guessed_age)))
                updated_count += 1
                time.sleep(1) # 避免触发速率限制

    if updated_count > 0:
        g.serialize(destination=QUEST_TTL_PATH, format="turtle")
        print(f"\n✅ 成功补齐并保存了 {updated_count} 个目标的年龄段！")
    else:
        print("\n✨ 所有目标都已有年龄段，无需修补。")

if __name__ == "__main__":
    main()
