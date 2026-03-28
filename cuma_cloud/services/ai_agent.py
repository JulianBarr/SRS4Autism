import asyncio
import os
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv

from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field
from google import genai

from cuma_cloud.core.database import async_sessionmaker_factory
from cuma_cloud.models import IepCommunicationLog, RoleEnum, User, ChildProfile, IepAiDraft

# Setup logger
import logging

logger = logging.getLogger(__name__)

# Initialize Gemini Client
def get_gemini_client():
    # Load environment variables
    # Try finding .env in root directory
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from dotenv import load_dotenv
    load_dotenv(os.path.join(root_dir, '.env'))
    # Also load from current working directory just in case
    load_dotenv()
    
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY or GOOGLE_API_KEY is not set in environment variables.")
        return None
        
    return genai.Client(api_key=api_key)

# Definition of structured output Schema
class AICardResponse(BaseModel):
    analysis: str = Field(description="对当前群聊记录的简短分析总结")
    card_type: str = Field(description="推荐的卡片类型，例如 PHYSICAL_QUEST 或 DIGITAL_ANKI")
    topic: str = Field(description="推荐的干预主题，例如 红蓝积木区分")
    difficulty: int = Field(description="卡片难度等级，1-5")
    ai_message: str = Field(description="发在群聊里的回复话术，如检测到小明已掌握颜色区分...")
    macro_objective: str = Field(description="宏观目标", default="")
    phasal_objective: str = Field(description="阶段目标", default="")
    suggested_materials: list[str] = Field(description="教具准备建议", default_factory=list)
    teaching_steps: list[str] = Field(description="教学步骤", default_factory=list)
    home_generalization: str = Field(description="家庭泛化建议", default="")

async def trigger_ai_assistant(child_id: int, parent_log_id: int = None):
    """
    Asynchronous background task to trigger Gemini AI assistant
    Must use its own database session.
    """
    logger.info(f"🚀 Starting background AI task for child {child_id}, triggered by log {parent_log_id}...")
    
    client = get_gemini_client()
    if not client:
        logger.error("❌ Cannot start AI task: No Gemini API Key found.")
        return

    try:
        async with async_sessionmaker_factory() as session:
            # 1. Verify child_id
            child_stmt = select(ChildProfile.id).where(ChildProfile.id == child_id)
            child_result = await session.execute(child_stmt)
            if not child_result.scalar_one_or_none():
                logger.warning(f"⚠️ Child {child_id} not found. AI task aborted.")
                return
                
            # 2. Get context: Fetch recent 10 communication logs for child_id
            stmt = (
                select(IepCommunicationLog)
                .where(IepCommunicationLog.child_id == child_id)
                .options(selectinload(IepCommunicationLog.sender))
                .order_by(IepCommunicationLog.created_at.desc())
                .limit(10)
            )
            result = await session.execute(stmt)
            logs = result.scalars().all()
            # Reverse to chronological order
            logs.reverse()
            
            if not logs:
                logger.warning(f"⚠️ No IEP communication logs found for child {child_id}.")
                return

            # Build Chat History Context
            prompt_lines = []
            for log in logs:
                sender_role = log.sender.role.value if log.sender and log.sender.role else "unknown"
                time_str = log.created_at.strftime("%Y-%m-%d %H:%M:%S") if log.created_at else "未知时间"
                prompt_lines.append(f"[{time_str}] {sender_role}: {log.content}")
                
            chat_history = "\n".join(prompt_lines)
            
            logger.info("\n=== 📝 Recent Chat History ===")
            logger.info(chat_history)
            logger.info("=============================\n")

            # 3. Build System Instruction
            system_instruction = (
                "你是一位专业的自闭症 (ASD) 特教 AI 助教。你的任务是阅读家校群聊记录，"
                "分析儿童的干预进度，并基于 FSRS (Free Spaced Repetition Scheduler) "
                "算法思想，为家长推荐下一个阶段的干预卡片配置。"
            )

            prompt = (
                f"以下是最近的家校沟通记录：\n{chat_history}\n\n"
                "请根据上述记录进行分析，并输出 JSON 格式的推荐配置。包含对当前进度的分析总结、"
                "推荐的干预主题和卡片类型、难度等级(1-5)，以及你想发送到群聊里的回复消息。"
            )
            
            # 4 & 5. Call Gemini to Think and use structured output
            logger.info("🧠 Thinking with Gemini-2.5-pro...")
            try:
                response = client.models.generate_content(
                    model='gemini-2.5-pro',
                    contents=prompt,
                    config=genai.types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        response_mime_type="application/json",
                        response_schema=AICardResponse,
                    ),
                )
                
                # Parse JSON
                response_json = response.text
                logger.info(f"\n✨ Gemini Response JSON:\n{response_json}\n")
                
                # Pydantic validation
                ai_output = AICardResponse.model_validate_json(response_json)
                
            except Exception as e:
                logger.error(f"❌ Error calling Gemini API: {e}", exc_info=True)
                return
                
            import json
            ai_data = json.loads(response.text)
            
            # 将完整的结构化数据作为隐藏的 payload 传给前端
            payload_str = json.dumps(ai_data, ensure_ascii=False, indent=2)
            
            final_content = f"{ai_data.get('ai_message', '为您生成了最新的干预方案：')}\n\n```json\n{payload_str}\n```"

            # 6. Save draft to DB
            if parent_log_id:
                new_draft = IepAiDraft(
                    child_id=child_id,
                    parent_log_id=parent_log_id,
                    draft_content=final_content,
                    status="PENDING"
                )
                session.add(new_draft)
                await session.commit()
                logger.info("✅ Agent background task finished successfully. AI draft inserted.")
            else:
                logger.warning("⚠️ No parent_log_id provided, AI draft not saved.")
            
    except Exception as e:
        logger.error(f"❌ Unhandled exception in trigger_ai_assistant: {e}", exc_info=True)
