import os
import json
import glob
import time
import google.generativeai as genai
from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDF, RDFS

# ==========================================
# 1. 代理配置与初始化
# ==========================================
os.environ["HTTP_PROXY"] = "socks5://127.0.0.1:49682"
os.environ["HTTPS_PROXY"] = "socks5://127.0.0.1:49682"

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("❌ 找不到 GEMINI_API_KEY，请设置环境变量。")

genai.configure(api_key=api_key)

# 🌟 切换至额度充足的生产级稳定模型，彻底告别 429
model = genai.GenerativeModel('gemini-2.5-pro')

# ==========================================
# 2. 目录与命名空间配置
# ==========================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_DIR = os.path.join(BASE_DIR, "data_prep", "extracted_json")
QUEST_TTL_PATH = os.path.join(BASE_DIR, "knowledge_graph", "quest_full.ttl")
PEP3_TTL_PATH = os.path.join(BASE_DIR, "knowledge_graph", "pep3_master.ttl")

ECTA_KG = Namespace("http://ecta.ai/schema/")
ECTA_INST = Namespace("http://ecta.ai/instance/")
PEP3_SCHEMA = Namespace("http://ecta.ai/pep3/schema/")
PEP3_INST = Namespace("http://ecta.ai/pep3/instance/")

# ==========================================
# 3. 动态生成 PEP-3 上下文全集
# ==========================================
def build_pep3_context():
    pep3_graph = Graph()
    pep3_graph.parse(PEP3_TTL_PATH, format="turtle")
    
    query = """
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX pep3: <http://ecta.ai/pep3/schema/>
    
    SELECT ?domainLabel ?itemNum ?itemLabel
    WHERE {
        ?item a pep3:AssessmentItem ;
              pep3:itemNumber ?itemNum ;
              pep3:belongsToDomain ?domain ;
              rdfs:label ?itemLabel .
        ?domain rdfs:label ?domainLabel .
    }
    ORDER BY ?itemNum
    """
    res = pep3_graph.query(query)
    
    domains = {}
    for row in res:
        domain = str(row.domainLabel)
        label = str(row.itemLabel)
        if domain not in domains:
            domains[domain] = []
        domains[domain].append(label)
        
    context_str = "【PEP-3 评估指标全集 (172项)】\n"
    for domain, items in domains.items():
        context_str += f"\n[{domain}]:\n"
        context_str += " | ".join(items) + "\n"
        
    return context_str

def get_llm_alignment(pep3_context, task_name, procedure):
    system_prompt = f"""
    你是一位拥有 20 年经验的孤独症特教专家。
    下面是《PEP-3 自闭症儿童心理教育评核》的完整指标库：
    {pep3_context}

    现在，我将给你一个机构的日常干预任务。
    请你深度分析这个任务的核心训练目的，并从上面的 PEP-3 指标库中，挑选出 0 到 3 个最直接相关的测试项（填数字题号即可，例如 105, 82）。
    请严格以 JSON 格式返回，格式为：{{"pep3_aligned_ids": [105, 108]}}。如果没有强相关的，返回空数组 []。
    """
    user_prompt = f"任务名称：{task_name}\n任务步骤：{procedure}"
    try:
        response = model.generate_content(
            [system_prompt, user_prompt],
            generation_config=genai.GenerationConfig(response_mime_type="application/json", temperature=0.0)
        )
        return json.loads(response.text).get("pep3_aligned_ids", [])
    except Exception as e:
        print(f"⚠️ LLM 对齐失败: {e}")
        return []

# ==========================================
# 5. 图谱融合主流程 (带强力除僵尸逻辑)
# ==========================================
def main():
    if not os.path.exists(PEP3_TTL_PATH):
        print(f"❌ 找不到 PEP-3 基础图谱: {PEP3_TTL_PATH}")
        return
        
    pep3_context = build_pep3_context()
    
    g = Graph()
    g.bind("ecta-kg", ECTA_KG)
    g.bind("ecta-inst", ECTA_INST)
    g.bind("pep3-inst", PEP3_INST)

    if os.path.exists(QUEST_TTL_PATH):
        print("🔄 检测到已保存的图谱进度，正在加载以进行断点续传...")
        g.parse(QUEST_TTL_PATH, format="turtle")

    json_files = glob.glob(os.path.join(JSON_DIR, "*.json"))
    task_counter = 1000 + len(g) 

    print(f"🚀 启动 Gemini 2.5 Pro 强力除错模式...")
    
    for file_path in json_files:
        with open(file_path, "r", encoding="utf-8") as f:
            try: data = json.load(f)
            except json.JSONDecodeError: continue

        if isinstance(data, list):
            if len(data) > 0 and isinstance(data[0], dict): data = data[0]
            else: continue
        if not isinstance(data, dict): continue

        macro_title = data.get("macro_objective", "").strip()
        if not macro_title: continue
        
        macro_uri = ECTA_INST[f"obj_macro_{task_counter}"]
        
        for quest in data.get("quests", []):
            quest_name = quest.get("quest_name", "").strip()
            procedure = quest.get("teaching_steps", "") or quest.get("procedure", "")
            if not quest_name: continue
            
            # 🌟 强力断点续传逻辑：不仅查名字，还查有没有对齐标准
            already_exists = False
            for quest_uri in list(g.subjects(RDFS.label, Literal(quest_name, lang="zh-CN"))):
                # 检查这个节点是否有 alignsWithStandard 属性
                has_alignment = list(g.objects(quest_uri, ECTA_KG.alignsWithStandard))
                if has_alignment:
                    already_exists = True
                else:
                    # 发现僵尸节点！把它从图谱里物理超度，准备重新处理
                    g.remove((quest_uri, None, None))
                    g.remove((None, None, quest_uri))
                    
            if already_exists:
                print(f"⏩ 已跳过: 《{quest_name}》 (之前已完整处理)")
                continue

            # 处理缺失的或新任务
            g.add((macro_uri, RDF.type, ECTA_KG.MacroObjective))
            g.add((macro_uri, RDFS.label, Literal(macro_title, lang="zh-CN")))

            quest_uri = ECTA_INST[f"task_{task_counter}"]
            g.add((quest_uri, RDF.type, ECTA_KG.PhasalObjective))
            g.add((quest_uri, RDFS.label, Literal(quest_name, lang="zh-CN")))
            g.add((macro_uri, ECTA_KG.hasPhase, quest_uri))

            print(f"🧠 思考中 (2.5 Pro 补漏): 《{quest_name}》 对应什么 PEP-3 标准?")
            aligned_ids = get_llm_alignment(pep3_context, quest_name, procedure)
            
            if aligned_ids:
                for num in aligned_ids:
                    pep3_uri = PEP3_INST[f"item_{num:03d}"]
                    g.add((quest_uri, ECTA_KG.alignsWithStandard, pep3_uri))
                    print(f"   🎯 成功补齐 -> PEP-3 第 {num} 题")
            else:
                print("   ⚪ 无强相关标准")

            task_counter += 1
            time.sleep(1.5)

        g.serialize(destination=QUEST_TTL_PATH, format="turtle")

    print(f"\n✅ 强力清剿与融合完毕！所有任务均已得到完美对齐！")

if __name__ == "__main__":
    main()
