import logging
import sys
import json

# --- 绝对防弹的 Logger 配置 ---
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG) # 确保 DEBUG 级别被放行
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('\n🚀 [%(levelname)s] %(message)s\n')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
# ------------------------------
import google.generativeai as genai
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query

from pydantic import BaseModel, Field
from app.utils.oxigraph_utils import get_kg_store
from scripts.daily_scheduler import record_feedback, find_child_profile, find_weakest_domain, get_db_path, get_target_milestone_uri
from datetime import datetime

router = APIRouter(prefix="/api/quests", tags=["Quests"])

class QuestGenerateRequest(BaseModel):
    milestone_uri: str = Field(..., description="e.g., http://cuma.ai/instance/vbmapp/echoic_1_m")
    child_context: Optional[str] = Field(None, description="e.g., 喜欢小汽车，注意力较短")
    child_id: Optional[str] = Field(None, description="Child profile ID")
    child_name: Optional[str] = Field(None, description="Child profile name")
    localize: Optional[bool] = Field(False, description="Whether to inject child specific context into the prompt")

class AutoGenerateQuestRequest(BaseModel):
    child_id: Optional[str] = Field(None, description="Child profile ID")
    child_name: Optional[str] = Field(None, description="Child profile name")
    localize: Optional[bool] = Field(False, description="Whether to inject child specific context into the prompt")

import os

CUSTOM_QUESTS_FILE = os.path.join(os.path.dirname(__file__), "../../../data/custom_quests.json")
DRAFT_QUESTS_FILE = os.path.join(os.path.dirname(__file__), "../../../data/draft_quests.json")

def load_custom_quests():
    if os.path.exists(CUSTOM_QUESTS_FILE):
        try:
            with open(CUSTOM_QUESTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_custom_quest(quest_data):
    quests = load_custom_quests()
    # Prevent duplicate custom quests for the same child.
    new_sig = (
        str(quest_data.get("child_name") or ""),
        str(quest_data.get("label") or "").strip(),
        str(quest_data.get("teaching_steps") or "").strip(),
    )
    for q in quests:
        old_sig = (
            str(q.get("child_name") or ""),
            str(q.get("label") or "").strip(),
            str(q.get("teaching_steps") or "").strip(),
        )
        if old_sig == new_sig:
            return
    quests.append(quest_data)
    os.makedirs(os.path.dirname(CUSTOM_QUESTS_FILE), exist_ok=True)
    with open(CUSTOM_QUESTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(quests, f, ensure_ascii=False, indent=2)

def save_custom_quests(quests):
    os.makedirs(os.path.dirname(CUSTOM_QUESTS_FILE), exist_ok=True)
    with open(CUSTOM_QUESTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(quests, f, ensure_ascii=False, indent=2)

def load_draft_quests():
    if os.path.exists(DRAFT_QUESTS_FILE):
        try:
            with open(DRAFT_QUESTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_draft_quests(quests):
    os.makedirs(os.path.dirname(DRAFT_QUESTS_FILE), exist_ok=True)
    with open(DRAFT_QUESTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(quests, f, ensure_ascii=False, indent=2)

def _quest_signature(item: Dict[str, Any]) -> str:
    title = str(item.get("quest_title") or item.get("label") or "").strip().casefold()
    objective = str(item.get("objective") or "").strip().casefold()
    steps = item.get("steps") or []
    normalized_steps = [str(s).strip().casefold() for s in steps if str(s).strip()]
    child_name = str(item.get("child_name") or "").strip().casefold()
    return json.dumps(
        {
            "child_name": child_name,
            "title": title,
            "objective": objective,
            "steps": normalized_steps,
        },
        ensure_ascii=False,
        sort_keys=True,
    )

def _draft_belongs_to_child(draft: Dict[str, Any], child_id: Optional[str], child_name: Optional[str]) -> bool:
    draft_child_id = str(draft.get("child_id") or "").strip()
    draft_child_name = str(draft.get("child_name") or "").strip().casefold()
    req_child_id = str(child_id or "").strip()
    req_child_name = str(child_name or "").strip().casefold()

    # Legacy records may miss child metadata. Keep them visible so they can be reviewed/cleaned.
    if not draft_child_id and not draft_child_name:
        return True

    if req_child_id:
        if draft_child_id:
            return draft_child_id == req_child_id
        if req_child_name and draft_child_name:
            return draft_child_name == req_child_name
        return False

    if req_child_name:
        if draft_child_name:
            return draft_child_name == req_child_name
        return False

    return True

@router.get("/drafts")
async def get_drafts(
    child_id: Optional[str] = Query(None),
    child_name: Optional[str] = Query(None),
):
    """
    Get current generated quest drafts for review.
    """
    drafts = load_draft_quests()
    if child_id or child_name:
        drafts = [d for d in drafts if _draft_belongs_to_child(d, child_id, child_name)]
    # Defensive dedupe for polluted legacy data.
    seen = set()
    unique_drafts = []
    for d in drafts:
        sig = _quest_signature(d)
        if sig in seen:
            continue
        seen.add(sig)
        unique_drafts.append(d)
    drafts = unique_drafts
    return drafts

@router.put("/drafts/{draft_id}")
async def update_draft(draft_id: str, request_data: dict):
    """Persist parent edits on draft content."""
    draft_quests = load_draft_quests()
    updated = False
    for i, draft in enumerate(draft_quests):
        if draft.get("quest_id") == draft_id:
            draft_quests[i] = {
                **draft,
                "quest_title": request_data.get("quest_title", draft.get("quest_title")),
                "objective": request_data.get("objective", draft.get("objective")),
                "steps": request_data.get("steps", draft.get("steps", [])),
            }
            updated = True
            break
    if not updated:
        raise HTTPException(status_code=404, detail="Draft not found")
    save_draft_quests(draft_quests)
    return {"status": "success", "message": f"Draft {draft_id} updated"}

@router.get("/custom")
async def get_custom_quests(
    child_name: Optional[str] = Query(None),
):
    """Get approved custom quests, optionally filtered by child."""
    custom_quests = load_custom_quests()
    if child_name:
        normalized = str(child_name).strip().casefold()
        custom_quests = [
            q for q in custom_quests
            if not str(q.get("child_name") or "").strip()
            or str(q.get("child_name") or "").strip().casefold() == normalized
        ]
    return custom_quests

@router.put("/custom/{quest_id}")
async def update_custom_quest(quest_id: str, request_data: dict):
    """Persist edits for approved custom quests."""
    custom_quests = load_custom_quests()
    updated = False
    for i, quest in enumerate(custom_quests):
        if quest.get("quest_id") == quest_id:
            next_label = request_data.get("quest_title", quest.get("label"))
            next_objective = request_data.get("objective", quest.get("objective", ""))
            next_steps = request_data.get("steps", quest.get("steps", []))
            custom_quests[i] = {
                **quest,
                "label": next_label,
                "objective": next_objective,
                "steps": next_steps,
                "teaching_steps": "目的：" + str(next_objective or "") + "\n\n步骤：\n" + "\n".join(next_steps or []),
            }
            updated = True
            break
    if not updated:
        raise HTTPException(status_code=404, detail="Custom quest not found")
    save_custom_quests(custom_quests)
    return {"status": "success", "message": f"Custom quest {quest_id} updated"}

@router.delete("/custom/{quest_id}")
async def delete_custom_quest(quest_id: str):
    """Remove an approved custom quest (used to cleanup duplicates)."""
    custom_quests = load_custom_quests()
    next_quests = [q for q in custom_quests if q.get("quest_id") != quest_id]
    if len(next_quests) == len(custom_quests):
        raise HTTPException(status_code=404, detail="Custom quest not found")
    save_custom_quests(next_quests)
    return {"status": "success", "message": f"Custom quest {quest_id} deleted"}

@router.post("/drafts/{draft_id}/approve")
async def approve_draft(draft_id: str, request_data: dict = None):
    """
    Approve a generated quest draft and move it to active quests.
    """
    logger.info(f"Approved draft {draft_id}")
    draft_quests = load_draft_quests()
    approved_quest = None
    for i, q in enumerate(draft_quests):
        if q.get("quest_id") == draft_id:
            approved_quest = q
            del draft_quests[i]
            break
    if not approved_quest:
        raise HTTPException(status_code=404, detail="Draft not found or already approved")
    save_draft_quests(draft_quests)

    if approved_quest:
        merged_quest = {
            **approved_quest,
            **(request_data or {}),
        }
        # Convert draft format to DailyDeck pending format
        custom_quest = {
            "quest_id": f"custom_{draft_id}_{os.urandom(4).hex()}",
            "label": merged_quest.get("quest_title", "自定义任务"),
            "pep3_standard": merged_quest.get("domain", "家长特制"),
            "pep3_items": [],
            "suggested_materials": ["详见步骤"],
            "teaching_steps": "目的：" + merged_quest.get("objective", "") + "\n\n步骤：\n" + "\n".join(merged_quest.get("steps", [])),
            "quest_title": merged_quest.get("quest_title", "自定义任务"),
            "objective": merged_quest.get("objective", ""),
            "steps": merged_quest.get("steps", []),
            "source": "custom",
            "child_id": merged_quest.get("child_id"),
            "child_name": merged_quest.get("child_name"),
            "hhs_source_label": merged_quest.get("hhs_source_label"),
        }
        save_custom_quest(custom_quest)

        # NEW: Record initial state of the custom quest into fsrs_states
        if custom_quest.get("child_name") and custom_quest.get("quest_id"):
            try:
                child_name_to_record = custom_quest["child_name"]
                quest_id_to_record = custom_quest["quest_id"]
                logger.info(f"Attempting to record FSRS state for child: {child_name_to_record}, quest_id: {quest_id_to_record}")
                record_feedback(
                    child_name=child_name_to_record,
                    quest_id=quest_id_to_record,
                    prompt_level="独立完成"
                )
                logger.info(f"Successfully recorded initial FSRS state for approved custom quest {quest_id_to_record} for child {child_name_to_record}")
            except Exception as e:
                logger.error(f"Failed to record initial FSRS state for custom quest {custom_quest['quest_id']} for child {custom_quest['child_name']}: {e}", exc_info=True) # Log full traceback
        
    return {"status": "success", "message": f"Draft {draft_id} approved"}

@router.post("/drafts/{draft_id}/reject")
async def reject_draft(draft_id: str):
    """
    Reject a generated quest draft.
    """
    logger.info(f"Rejected draft {draft_id}")
    draft_quests = load_draft_quests()
    draft_quests = [q for q in draft_quests if q.get("quest_id") != draft_id]
    save_draft_quests(draft_quests)
    return {"status": "success", "message": f"Draft {draft_id} rejected"}

def _summarize_extracted_for_log(extracted: Any) -> str:
    """Short string for logs; avoid dumping huge JSON."""
    if not isinstance(extracted, dict):
        return repr(type(extracted).__name__)
    keys = sorted(extracted.keys())
    cc = extracted.get("child_context")
    if isinstance(cc, str):
        has_child_context = bool(cc.strip())
    else:
        has_child_context = cc is not None
    return json.dumps(
        {
            "keys": keys,
            "has_child_context": has_child_context,
            "has_pep3_baseline": bool(extracted.get("pep3_baseline")),
        },
        ensure_ascii=False,
    )


@router.post("/generate")
async def generate_quest(request: QuestGenerateRequest):
    """
    Generate a daily quest based on the provided VB-MAPP milestone URI.
    """
    store = get_kg_store()

    # 1. SPARQL 反向查询 (寻找目标和关联活动)
    # Note: Using OPTIONAL on the hhs_goal part as well to allow fallback to just getting the milestone label
    # if no HHS goal aligns with it.
    query = f"""
    PREFIX cuma-schema: <http://cuma.ai/schema/>
    PREFIX hhs-ont: <http://example.org/hhs/ontology#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?hhs_goal ?goal_label ?activity ?material ?milestone_label
    WHERE {{
        OPTIONAL {{
            ?hhs_goal cuma-schema:alignsWith <{request.milestone_uri}> .
            ?hhs_goal rdfs:label ?goal_label .
            OPTIONAL {{ ?hhs_goal hhs-ont:hasActivity ?activity . }}
            OPTIONAL {{ ?hhs_goal hhs-ont:hasMaterial ?material . }}
        }}
        OPTIONAL {{
            <{request.milestone_uri}> rdfs:label ?milestone_label .
        }}
    }}
    """
    
    try:
        results = list(store.query(query))
    except Exception as e:
        logger.error(f"SPARQL query failed: {e}")
        raise HTTPException(status_code=500, detail="Query execution failed")

    # If no results at all, we can't do anything
    if not results:
        raise HTTPException(status_code=404, detail="No HHS goal or milestone found for this URI")

    # Filter out empty bindings that might result from all OPTIONALs failing
    # In rdflib, results row objects behave differently. Sometimes they are QuerySolution dict-like objects, 
    # sometimes just namedtuples depending on parser.
    # Let's use a safe extraction method.
    def get_node(row, key):
        try:
            return row[key]
        except (KeyError, TypeError, Exception):
            return getattr(row, key, None)
            
    valid_results = [r for r in results if get_node(r, "goal_label") or get_node(r, "milestone_label")]
    if not valid_results:
        # Check if we can extract a name from the URI as a last resort
        uri_parts = str(request.milestone_uri).split("/")
        if uri_parts:
            fallback_label = uri_parts[-1].replace("_", " ").title()
            valid_results = [{"milestone_label": type('obj', (object,), {'value': fallback_label})()}]
        else:
            raise HTTPException(status_code=404, detail="No HHS goal or milestone found for this URI")

    # 2. 提取与清洗
    target_skill_text = ""
    hhs_source_label = ""
    expert_activities_set = set()
    expert_materials_set = set()

    # Aggregate all activities and materials
    for row in valid_results:
        if isinstance(row, dict): # Handle the fallback case
             milestone_label_node = row.get("milestone_label")
             if milestone_label_node and not target_skill_text:
                 target_skill_text = milestone_label_node.value
             continue
        
        goal_label_node = get_node(row, "goal_label")
        milestone_label_node = get_node(row, "milestone_label")
        
        if goal_label_node is not None:
            hhs_source_label = goal_label_node.value
            if not target_skill_text:
                target_skill_text = goal_label_node.value
        elif milestone_label_node is not None and not target_skill_text:
            target_skill_text = milestone_label_node.value
                
        activity_node = get_node(row, "activity")
        if activity_node is not None:
            expert_activities_set.add(activity_node.value)
            
        material_node = get_node(row, "material")
        if material_node is not None:
            expert_materials_set.add(material_node.value)
            
    expert_activities = list(expert_activities_set)
    expert_materials = list(expert_materials_set)

    import random

    DEFAULT_ACTIVITY_SHELLS = [
        "玩具小动物喂食游戏",
        "神秘摸彩箱游戏",
        "扮演小医生/过家家",
        "寻宝游戏 (在房间内找寻)",
        "推车/运货游戏",
        "钓鱼游戏 (磁性小鱼)",
    ]

    kg_activity_count = len(expert_activities)
    kg_material_count = len(expert_materials)
    used_activity_shell_fallback = False
    used_material_default_fallback = False

    # 👇👇👇 请将这段 Debug 代码插入到构建 system_prompt 之前 👇👇👇
    logger.debug("="*60)
    logger.debug(f"🎯 正在为目标生成 Quest: 【{target_skill_text}】")
    logger.debug(f"📚 从图谱查到的活动 (Activities): {expert_activities}")
    logger.debug(f"🛠️ 从图谱查到的材料 (Materials): {expert_materials}")
    logger.debug("="*60)
    # 👆👆👆 ======================================================= 👆👆👆

    if not expert_activities:
        used_activity_shell_fallback = True
        expert_activities = [random.choice(DEFAULT_ACTIVITY_SHELLS)]

    if not expert_materials:
        used_material_default_fallback = True
        expert_materials = ["家里常见的玩具", "日常用品 (如碗、勺子、绘本)"]

    import sqlite3
    
    db_path = get_db_path()
    db_child_context = ""
    
    if request.localize and (request.child_id or request.child_name):
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        lookup_row = None
        if request.child_id:
            cur.execute("SELECT interests, character_roster FROM profiles WHERE id = ?", (request.child_id,))
            lookup_row = cur.fetchone()
        
        if not lookup_row and request.child_name:
            cur.execute("SELECT interests, character_roster FROM profiles WHERE name = ?", (request.child_name,))
            lookup_row = cur.fetchone()
            
        conn.close()
        
        if lookup_row:
            interests_list = []
            if lookup_row["interests"]:
                try:
                    parsed = json.loads(lookup_row["interests"])
                    if isinstance(parsed, list):
                        interests_list = parsed
                    elif isinstance(parsed, str):
                        interests_list = [parsed]
                except Exception:
                    interests_list = [str(lookup_row["interests"])]
                    
            chars_list = []
            if lookup_row["character_roster"]:
                try:
                    parsed = json.loads(lookup_row["character_roster"])
                    if isinstance(parsed, list):
                        chars_list = parsed
                    elif isinstance(parsed, str):
                        chars_list = [parsed]
                except Exception:
                    chars_list = [str(lookup_row["character_roster"])]
                    
            parts = []
            if interests_list:
                parts.append(f"孩子非常喜欢{', '.join(str(i) for i in interests_list)}")
            if chars_list:
                parts.append(f"最爱的角色是{', '.join(str(c) for c in chars_list)}")
                
            if parts:
                db_child_context = "，".join(parts) + "。"
                
    if request.localize:
        final_child_context = db_child_context or request.child_context or "无特定偏好"
    else:
        final_child_context = "无特定偏好"

    # 3. 调用 Gemini 模型
    system_prompt = f"""
你是一个资深的 BCBA（应用行为分析师）。你现在需要对协康会（HHS）的专家建议进行改编，为家长编写居家干预说明。

【训练目标】: {target_skill_text}
【专家原始建议】: {expert_activities} (这是你的唯一合法参考，不准自行发明新游戏机制)
【建议教具】: {expert_materials} (这是你的唯一合法教具参考，严禁自行发明新教具)
"""

    if request.localize and final_child_context != "无特定偏好":
        system_prompt += f"""
【孩子个性化上下文】: {final_child_context}

你的职责：
1. **核心逻辑不动**：保持 HHS 专家建议中的干预步骤和物理操作逻辑。如果专家建议里写的是“出示形状板”，操作上仍然必须是出示形状板。
2. **套上兴趣外壳**：将游戏的情境、角色、或对话内容，巧妙地替换为孩子喜爱的【{final_child_context}】。
3. **示例**：如果目标是‘辨认形状’且孩子喜欢‘小猪佩奇’，可以将教具描述为‘佩奇的形状饼干’，将指令改为‘把圆形给佩奇吃’。
4. **严格遵守教具建议**：必须使用【建议教具】中列出的材料（可在此基础上加糖，如上面示例的形状板变成饼干）。如果列表中为空，则引导家长使用“家里常见的玩具”或“日常用品”。严禁自行发明或要求家长制作复杂的教具。
5. **口语化改编**：将专家生硬的文字转化为家长听得懂、好操作的“第一步、第二步、第三步”。

必须返回 JSON 格式：{{ "quest_title": "...", "objective": "...", "setup": "需要的日常道具 (务必基于【建议教具】列出，可进行兴趣外壳包装，严禁要求手工制作复杂教具)", "steps": [...] }}
"""
    else:
        system_prompt += f"""
你的职责：
1. **核心逻辑不动**：保持 HHS 专家建议中的干预步骤和物理操作逻辑。如果专家建议里写的是“出示形状板”，操作上仍然必须是出示形状板。
2. **严格遵守教具建议**：必须使用【建议教具】中列出的材料。如果列表中为空，则引导家长使用“家里常见的玩具”或“日常用品”。严禁自行发明或要求家长制作复杂的教具。
3. **口语化改编**：将专家生硬的文字转化为家长听得懂、好操作的“第一步、第二步、第三步”。不要添加特定角色的外壳。

必须返回 JSON 格式：{{ "quest_title": "...", "objective": "...", "setup": "需要的日常道具 (务必基于【建议教具】列出，严禁要求手工制作复杂教具)", "steps": [...] }}
"""

    llm_model_name = "gemini-3.1-pro-preview"
    raw_child_ctx = final_child_context
    child_ctx_stripped = raw_child_ctx.strip()
    child_ctx_for_log = child_ctx_stripped or "(none)"
    if len(child_ctx_for_log) > 1200:
        child_ctx_for_log = child_ctx_for_log[:1200] + "…[truncated]"

    logger.info(
        "\n"
        "================================================================================\n"
        "QUEST /generate — DATA USED BEFORE LLM\n"
        "================================================================================\n"
        "milestone_uri=%s\n"
        "child_id=%s child_name=%s\n"
        "child_context_len=%s child_context=%s\n"
        "sparql_row_count=%s\n"
        "kg_distinct_activity_strings=%s kg_distinct_material_strings=%s\n"
        "used_activity_shell_fallback=%s used_material_default_fallback=%s\n"
        "target_skill_text=%s\n"
        "hhs_source_label=%s\n"
        "expert_activities_for_prompt=%s\n"
        "expert_materials_for_prompt=%s\n"
        "--------------------------------------------------------------------------------\n"
        "SPARQL (embedded Oxigraph):\n%s\n"
        "--------------------------------------------------------------------------------\n"
        "FULL SYSTEM PROMPT → %s\n"
        "--------------------------------------------------------------------------------\n"
        "%s\n"
        "================================================================================\n",
        request.milestone_uri,
        request.child_id,
        request.child_name,
        len(raw_child_ctx),
        child_ctx_for_log,
        len(results),
        kg_activity_count,
        kg_material_count,
        used_activity_shell_fallback,
        used_material_default_fallback,
        target_skill_text,
        hhs_source_label,
        json.dumps(expert_activities, ensure_ascii=False),
        json.dumps(expert_materials, ensure_ascii=False),
        query.strip(),
        llm_model_name,
        system_prompt.strip(),
    )

    try:
        model = genai.GenerativeModel(llm_model_name)

        response = model.generate_content(
            system_prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
            ),
        )

        # 4. 返回数据
        raw_text = response.text
        try:
            quest_data = json.loads(raw_text)
        except json.JSONDecodeError:
            # Fallback if the response is not valid JSON
            logger.error(f"Failed to parse JSON from LLM: {raw_text}")
            raise ValueError("LLM did not return valid JSON")

        if isinstance(quest_data, list):
            if len(quest_data) > 0:
                quest_data = quest_data[0]
                logger.warning("LLM returned a list of quests. Using the first one.")
            else:
                logger.error("LLM returned an empty list.")
                raise ValueError("LLM returned an empty list")

        if not isinstance(quest_data, dict):
            logger.error(f"LLM returned an unexpected type: {type(quest_data)}. Content: {quest_data}")
            raise ValueError("LLM returned an unexpected JSON structure")

        logger.info(
            "QUEST /generate — LLM OUTPUT: quest_title=%r objective_len=%s setup_len=%s steps=%s",
            quest_data.get("quest_title"),
            len(str(quest_data.get("objective") or "")),
            len(str(quest_data.get("setup") or "")),
            len(quest_data.get("steps") or []),
        )

        # Assign a unique quest_id and save as a draft
        quest_id = f"draft_{os.urandom(4).hex()}"
        quest_data["quest_id"] = quest_id
        quest_data["source"] = "draft"
        quest_data["child_id"] = request.child_id
        quest_data["child_name"] = request.child_name
        quest_data["hhs_source_label"] = hhs_source_label
        quest_data["milestone_uri"] = request.milestone_uri
        save_draft_quests([*load_draft_quests(), quest_data])
        
        return quest_data
        
    except Exception as e:
        logger.error(f"Gemini generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Quest generation failed: {str(e)}")


@router.post("/auto-generate")
async def auto_generate_quest(request: AutoGenerateQuestRequest):
    """
    Automatically generate a daily quest based on the child's weakest PEP-3 domain.
    """
    if not (request.child_id and str(request.child_id).strip()) and not (
        request.child_name and str(request.child_name).strip()
    ):
        raise HTTPException(
            status_code=400,
            detail="Provide child_id (profiles.id from the selector) or exact child_name",
        )

    db_path = get_db_path()
    # Prefer stable primary key from the header — resolution is exact id, then exact name only.
    lookup = (str(request.child_id).strip() if request.child_id else "") or (
        str(request.child_name).strip() if request.child_name else ""
    )
    profile_row = find_child_profile(db_path, lookup)

    if not profile_row:
        raise HTTPException(status_code=404, detail=f"Child profile not found for {request.child_name or request.child_id}")
    
    profile_id, _, extracted_data = profile_row

    # 1. Target Milestone Selection based on Survey Progress
    try:
        milestone_uri, milestone_source = get_target_milestone_uri(profile_id, db_path)

        if milestone_uri:
            if milestone_source == "survey_review_pass":
                logger.info("[INFO] Target selected from PASSED milestone for review: %s", milestone_uri)
            elif milestone_source == "survey_learning":
                logger.info("[INFO] Target selected from explicit LEARNING state: %s", milestone_uri)
            # Deduced log is printed inside get_target_milestone_uri, but we can log it here too if needed

        if not milestone_uri:
            raise HTTPException(
                status_code=400,
                detail="No survey records found. Please complete the initial survey to establish a baseline before generating quests."
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error determining milestone target: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error during milestone selection.")

    # Context extraction for LLM
    if request.localize:
        interests = extracted_data.get("interests", [])
        if isinstance(interests, list) and interests:
            child_context_str = "孩子的兴趣爱好包含: " + ", ".join(str(i) for i in interests)
        elif isinstance(interests, str) and interests.strip():
            child_context_str = "孩子的兴趣爱好包含: " + interests.strip()
        else:
            child_context_str = "无特定偏好"
    else:
        child_context_str = "无特定偏好"

    child_ctx_preview = child_context_str
    if len(child_ctx_preview) > 1200:
        child_ctx_preview = child_ctx_preview[:1200] + "…[truncated]"

    logger.info(
        "\n"
        "================================================================================\n"
        "QUEST /auto-generate — RESOLVED INPUT (before /generate)\n"
        "================================================================================\n"
        "lookup=%s profile_id=%s profile_name=%s\n"
        "milestone_source=%s milestone_uri=%s\n"
        "extracted_data_summary=%s\n"
        "child_context_passed_to_llm_len=%s child_context=%s\n"
        "================================================================================\n",
        lookup,
        profile_id,
        profile_row[1],
        milestone_source,
        milestone_uri,
        _summarize_extracted_for_log(extracted_data),
        len(child_context_str),
        child_ctx_preview,
    )

    # Use the existing generate_quest logic
    generate_request = QuestGenerateRequest(
        milestone_uri=milestone_uri,
        child_context=child_context_str,
        child_id=profile_id,
        child_name=request.child_name or profile_row[1],
        localize=request.localize,
    )

    return await generate_quest(generate_request)
