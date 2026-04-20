#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
import time
from pathlib import Path
import google.generativeai as genai
from rdflib import Graph, Namespace

# --- 配置区 ---
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent

# 尝试兼容不同的文件路径结构
VBMAPP_TTL = PROJECT_ROOT / "scripts" / "data_extraction" / "vbmapp_woven_ontology.ttl"
OUTPUT_TTL = PROJECT_ROOT / "knowledge_graph" / "survey_parent_full.ttl"

MODEL_NAME = "gemini-3.1-flash-lite-preview" 
BATCH_SIZE = 5

CUMA_SURVEY_URI = "http://cuma.ai/schema/survey/"
SURVEY_INST_URI = "http://cuma.ai/instance/survey/parent#"
RDFS_URI = "http://www.w3.org/2000/01/rdf-schema#"
XSD_URI = "http://www.w3.org/2001/XMLSchema#"
VBMAPP_SCHEMA_URI = "http://cuma.ai/schema/vbmapp/"

CUMA_SURVEY = Namespace(CUMA_SURVEY_URI)
SURVEY_INST = SURVEY_INST_URI

def get_deterministic_ids(milestone_uri):
    """根据里程碑 URI 生成确定的问卷和选项 ID"""
    base_id = str(milestone_uri).split('/')[-1].replace('-', '_')
    q_uri = f"{SURVEY_INST}{base_id}_q"
    opt_uris = [f"{q_uri}_opt{i}" for i in [1, 2, 3]]
    return q_uri, opt_uris

def build_prompt(batch_nodes):
    """使用严格的 One-Shot Template，强制 LLM 像填空题一样输出，杜绝幻觉"""
    nodes_info = []
    for node in batch_nodes:
        q_uri, opt_uris = get_deterministic_ids(node['uri'])
        num_match = re.search(r'(\d+)', node['label'])
        is_bottleneck = (node['level'] == 1 and num_match and num_match.group(1) in ['1', '5'])
        bottleneck_str = 'cuma-survey:isBottleneck "true"^^xsd:boolean ;' if is_bottleneck else ''
        
        info = f"""
### DATA TO CONVERT:
- Milestone: {node['label']}
- evaluatesNode: <{node['uri']}>
- Question URI: <{q_uri}>
- Option 1 URI: <{opt_uris[0]}>
- Option 2 URI: <{opt_uris[1]}>
- Option 3 URI: <{opt_uris[2]}>
- Bottleneck Line: {bottleneck_str}
"""
        nodes_info.append(info)

    return f"""
You are a BCBA expert. Convert the following VB-MAPP Milestones into parent-friendly survey questions. 
You MUST output ONLY valid Turtle (.ttl) code. 

CRITICAL RULE: You MUST strictly copy this EXACT format for EVERY question. Do not invent your own structures, classes, or syntax. Use {{child_name}} and {{pronoun}} in the text.

### EXACT TEMPLATE TO FOLLOW:
<[Question URI]> a cuma-survey:ParentQuestion ;
    cuma-survey:evaluatesNode <[evaluatesNode]> ;
    [Bottleneck Line (if applicable)]
    cuma-survey:promptTemplate "[English Question here]"@en, "[Chinese Question here]"@zh ;
    cuma-survey:hasOption <[Option 1 URI]>, <[Option 2 URI]>, <[Option 3 URI]> .

<[Option 1 URI]> a cuma-survey:Option ;
    cuma-survey:optionText "Cannot do it"@en, "无法完成"@zh ;
    cuma-survey:stateAction "FAIL" .

<[Option 2 URI]> a cuma-survey:Option ;
    cuma-survey:optionText "Needs prompts"@en, "需提示"@zh ;
    cuma-survey:stateAction "FAIL_PROMPT_DEPENDENT" .

<[Option 3 URI]> a cuma-survey:Option ;
    cuma-survey:optionText "Does it independently"@en, "独立完成"@zh ;
    cuma-survey:stateAction "PASS_NODE" .

{"".join(nodes_info)}
"""

def write_header():
    """写入标准头部，避免重复声明前缀"""
    if not OUTPUT_TTL.exists():
        # 确保目录存在
        OUTPUT_TTL.parent.mkdir(parents=True, exist_ok=True)
        header = f"""@prefix cuma-survey: <{CUMA_SURVEY_URI}> .
@prefix rdfs: <{RDFS_URI}> .
@prefix xsd: <{XSD_URI}> .
@prefix cuma-inst: <{SURVEY_INST_URI}> .

"""
        with open(OUTPUT_TTL, 'w', encoding='utf-8') as f:
            f.write(header)

def run_generation():
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel(MODEL_NAME)
    
    g = Graph()
    
    # 兼容查找逻辑：如果根目录下没有，尝试在当前脚本目录查找
    if not VBMAPP_TTL.exists():
        fallback_path = SCRIPT_DIR / "vbmapp_woven_ontology.ttl"
        if fallback_path.exists():
            g.parse(fallback_path, format="turtle")
        else:
            print(f"Error: Could not find ontology file at {VBMAPP_TTL} or {fallback_path}")
            return
    else:
        g.parse(VBMAPP_TTL, format="turtle")
    
    # 强大的 Checkpoint 逻辑
    done_uris = set()
    if OUTPUT_TTL.exists():
        with open(OUTPUT_TTL, 'r', encoding='utf-8') as f:
            content = f.read()
            # 必须匹配具体的 URI 来验证这道题真的做完了
            done_uris = set(re.findall(r'evaluatesNode\s+<(.*?)>', content))

    milestones = []
    # Dynamic injection of hexadecimal string constants
    query = f"""
    PREFIX vbmapp-schema: <{VBMAPP_SCHEMA_URI}>
    PREFIX rdfs: <{RDFS_URI}>
    SELECT ?s ?label ?desc ?level WHERE {{
        ?s a vbmapp-schema:Milestone ;
           rdfs:label ?label ;
           vbmapp-schema:description ?desc ;
           vbmapp-schema:level ?level .
    }} ORDER BY ?level ?s
    """
    
    for row in g.query(query):
        if str(row.s) not in done_uris:
            milestones.append({
                'uri': str(row.s),
                'label': str(row.label),
                'desc': str(row.desc),
                'level': int(row.level)
            })

    if not milestones:
        print("All milestones already processed.")
        return

    print(f"Total pending: {len(milestones)}. Starting generation...")
    write_header()

    for i in range(0, len(milestones), BATCH_SIZE):
        batch = milestones[i:i+BATCH_SIZE]
        print(f"Processing batch {i//BATCH_SIZE + 1}/{(len(milestones)+BATCH_SIZE-1)//BATCH_SIZE} ({batch[0]['label']}...)")
        
        prompt = build_prompt(batch)
        
        # 带指数退避的 API 请求逻辑
        while True:
            try:
                response = model.generate_content(prompt)
                
                # 更强壮的正则：匹配 \x60\x60\x60turtle, \x60\x60\x60ttl, 或仅仅是 \x60\x60\x60 (Hex编码防冲突)
                ttl_match = re.search(r'\x60\x60\x60(?:turtle|ttl)?\n(.*?)\n\x60\x60\x60', response.text, re.DOTALL | re.IGNORECASE)
                
                if ttl_match:
                    ttl_content = ttl_match.group(1)
                else:
                    # 如果 LLM 没有用代码块包裹，直接去除多余标记
                    ttl_content = response.text.replace('\x60\x60\x60turtle', '').replace('\x60\x60\x60ttl', '').replace('\x60\x60\x60', '')
                
                with open(OUTPUT_TTL, 'a', encoding='utf-8') as f:
                    f.write(f"\n# Batch {i//BATCH_SIZE + 1}\n")
                    f.write(ttl_content.strip() + "\n")
                
                time.sleep(4)
                break 
                
            except Exception as e:
                if "429" in str(e):
                    print(f"  [Rate Limit 429] 触发限流，休眠 15 秒后重试该批次...")
                    time.sleep(15)
                else:
                    print(f"  [API Error] {e}。休眠 5 秒后重试...")
                    time.sleep(5)

if __name__ == "__main__":
    run_generation()
