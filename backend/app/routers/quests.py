import logging
import json
import google.generativeai as genai
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query

from pydantic import BaseModel, Field
from app.utils.oxigraph_utils import get_kg_store
from scripts.daily_scheduler import record_feedback, find_child_profile, find_weakest_domain, get_db_path
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/quests", tags=["Quests"])

class QuestGenerateRequest(BaseModel):
    milestone_uri: str = Field(..., description="e.g., http://cuma.ai/instance/vbmapp/echoic_1_m")
    child_context: Optional[str] = Field(None, description="e.g., 喜欢小汽车，注意力较短")
    child_id: Optional[str] = Field(None, description="Child profile ID")
    child_name: Optional[str] = Field(None, description="Child profile name")

class AutoGenerateQuestRequest(BaseModel):
    child_id: Optional[str] = Field(None, description="Child profile ID")
    child_name: Optional[str] = Field(None, description="Child profile name")

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

@router.post("/generate")
async def generate_quest(request: QuestGenerateRequest):
    """
    Generate a daily quest based on the provided VB-MAPP milestone URI.
    """
    store = get_kg_store()

    # 1. SPARQL 反向查询
    query = f"""
    PREFIX cuma-schema: <http://cuma.ai/schema/>
    SELECT ?hhs_goal
    WHERE {{
        ?hhs_goal cuma-schema:alignsWith <{request.milestone_uri}> .
    }}
    """
    
    try:
        results = list(store.query(query))
    except Exception as e:
        logger.error(f"SPARQL query failed: {e}")
        raise HTTPException(status_code=500, detail="Query execution failed")

    if not results:
        raise HTTPException(status_code=404, detail="No HHS goal aligned with this milestone")

    # 2. 提取与清洗
    # Get the first match
    hhs_goal_uri = results[0]["hhs_goal"].value
    
    # Example URI: http://cuma.ai/instance/hhs/Goal_语言表达_模仿发声_模仿发声_如_哗_呠呠_汪汪
    # Extract the last segment
    last_segment = hhs_goal_uri.split("/")[-1]
    
    # Replace underscores with spaces
    target_skill_text = last_segment.replace("_", " ")
    logger.info(f"Retrieved target_skill_text: {target_skill_text}")

    # 3. 调用 Gemini 模型
    system_prompt = f"""
你是一个资深的 BCBA（应用行为分析师）。
今天孩子的训练目标是 (来源于协康会纲要)：{target_skill_text}
孩子的个人偏好：{request.child_context or "无特定偏好"}

请为家长设计一个 3-5 分钟的居家干预小游戏 (Quest)。
必须输出 JSON 格式，严格包含以下字段：
{{
  "quest_title": "吸引人的游戏名称",
  "objective": "一句话说明这个游戏在练什么",
  "setup": "需要的道具或环境准备",
  "steps": ["第一步", "第二步", "第三步"],
  "feedback_options": [
    {{"label": "A: 完全独立清晰地做到", "value": "A", "confidence_weight": 1.0}},
    {{"label": "B: 稍微延迟或在口头提示下做到", "value": "B", "confidence_weight": 0.6}},
    {{"label": "C: 需要大量夸张示范或肢体辅助", "value": "C", "confidence_weight": 0.2}},
    {{"label": "D: 完全没有反应或抗拒", "value": "D", "confidence_weight": 0.0}}
  ]
}}
注意：feedback_options 的内容必须固定为这四种程度（A/B/C/D），代表系统收集的贝叶斯证据强度。
"""

    try:
        model = genai.GenerativeModel('gemini-3.1-pro-preview')
        
        response = model.generate_content(
            system_prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
            )
        )
        
        # 4. 返回数据
        quest_data = json.loads(response.text)
        
        # Assign a unique quest_id and save as a draft
        quest_id = f"draft_{os.urandom(4).hex()}"
        quest_data["quest_id"] = quest_id
        quest_data["source"] = "draft"
        quest_data["child_id"] = request.child_id
        quest_data["child_name"] = request.child_name
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
    if not request.child_name and not request.child_id:
        raise HTTPException(status_code=400, detail="Child name or ID is required for auto-generation")
    
    db_path = get_db_path()
    profile_row = find_child_profile(db_path, request.child_name or request.child_id)

    if not profile_row:
        raise HTTPException(status_code=404, detail=f"Child profile not found for {request.child_name or request.child_id}")
    
    profile_id, _, extracted_data = profile_row
    weakest_domain_info = find_weakest_domain(extracted_data)

    if not weakest_domain_info:
        # Fallback to a generic milestone if no weakest domain is found
        # In a real system, you'd have a more sophisticated fallback mechanism
        logger.warning(f"No weakest domain found for child {request.child_name or request.child_id}, using a generic milestone.")
        milestone_uri = "http://cuma.ai/instance/vbmapp/listener_5_m" # Example generic milestone
    else:
        domain_code, _, _ = weakest_domain_info
        # For simplicity, map domain code back to a generic milestone URI
        # A more robust solution would query the KG for a specific milestone
        milestone_map = {
            "CVP": "http://cuma.ai/instance/vbmapp/visual_2_m",
            "EL": "http://cuma.ai/instance/vbmapp/echoic_1_m",
            "RL": "http://cuma.ai/instance/vbmapp/listener_5_m",
            "FM": "http://cuma.ai/instance/vbmapp/motor_2_m",
            "GM": "http://cuma.ai/instance/vbmapp/motor_1_m",
            "VMI": "http://cuma.ai/instance/vbmapp/visual_4_m",
            "AE": "http://cuma.ai/instance/vbmapp/social_1_m",
            "SR": "http://cuma.ai/instance/vbmapp/social_2_m",
            "CMB": "http://cuma.ai/instance/vbmapp/behavior_1_m",
            "CVB": "http://cuma.ai/instance/vbmapp/echoic_3_m",
        }
        milestone_uri = milestone_map.get(domain_code, "http://cuma.ai/instance/vbmapp/listener_5_m") # Default fallback

    # Use the existing generate_quest logic
    generate_request = QuestGenerateRequest(
        milestone_uri=milestone_uri,
        child_context=extracted_data.get("child_context"), # assuming this might exist in extracted_data
        child_id=profile_id,
        child_name=request.child_name or profile_row[1] # Use actual profile name if provided by request or from DB
    )

    return await generate_quest(generate_request)
