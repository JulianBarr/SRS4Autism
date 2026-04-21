import logging
import json
import google.generativeai as genai
from typing import Optional
from fastapi import APIRouter, HTTPException

from pydantic import BaseModel, Field
from app.utils.oxigraph_utils import get_kg_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/quests", tags=["Quests"])

class QuestGenerateRequest(BaseModel):
    milestone_uri: str = Field(..., description="e.g., http://cuma.ai/instance/vbmapp/echoic_1_m")
    child_context: Optional[str] = Field(None, description="e.g., 喜欢小汽车，注意力较短")

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
        return quest_data
        
    except Exception as e:
        logger.error(f"Gemini generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Quest generation failed: {str(e)}")
