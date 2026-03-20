import asyncio
import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv

# 加载 .env 环境变量
load_dotenv()

# 将项目根目录加入 sys.path 以便导入 cuma_cloud
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field
from google import genai

from cuma_cloud.core.database import async_sessionmaker_factory
from cuma_cloud.models import IepCommunicationLog, RoleEnum, User, ChildProfile

# 初始化 Gemini Client
api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("❌ Error: GEMINI_API_KEY or GOOGLE_API_KEY is not set in environment variables.")
    sys.exit(1)

client = genai.Client(api_key=api_key)

# 定义结构化输出的 Schema
class AICardResponse(BaseModel):
    analysis: str = Field(description="对当前群聊记录的简短分析总结")
    card_type: str = Field(description="推荐的卡片类型，如 FSRS_COGNITIVE")
    topic: str = Field(description="推荐的干预主题，例如 红蓝积木区分")
    difficulty: int = Field(description="卡片难度等级，1-5")
    ai_message: str = Field(description="发在群聊里的回复话术，如检测到小明已掌握颜色区分...")

async def run_agent_job(child_id: int = 1):
    print(f"🚀 Starting Gemini AI agent job for child {child_id}...")
    
    async with async_sessionmaker_factory() as session:
        # 1. 验证 child_id
        child_stmt = select(ChildProfile.id).where(ChildProfile.id == child_id)
        child_result = await session.execute(child_stmt)
        if not child_result.scalar_one_or_none():
            print(f"⚠️ Child {child_id} not found. Attempting to fallback to first available child...")
            fallback_child_stmt = select(ChildProfile.id).limit(1)
            fallback_child_result = await session.execute(fallback_child_stmt)
            child_id = fallback_child_result.scalar_one_or_none()
            if not child_id:
                print("❌ No children found in the database. Exiting.")
                return
            print(f"💡 Using fallback child_id: {child_id}")
            
        # 2. 获取上下文：查询 child_id 的最近 10 条沟通记录
        stmt = (
            select(IepCommunicationLog)
            .where(IepCommunicationLog.child_id == child_id)
            .options(selectinload(IepCommunicationLog.sender))
            .order_by(IepCommunicationLog.created_at.desc())
            .limit(10)
        )
        result = await session.execute(stmt)
        logs = result.scalars().all()
        # 倒序转正序
        logs.reverse()
        
        if not logs:
            print(f"⚠️ No IEP communication logs found for child {child_id}.")
            return

        # 构建聊天记录 Context
        prompt_lines = []
        for log in logs:
            sender_role = log.sender.role.value if log.sender and log.sender.role else "unknown"
            time_str = log.created_at.strftime("%Y-%m-%d %H:%M:%S") if log.created_at else "未知时间"
            prompt_lines.append(f"[{time_str}] {sender_role}: {log.content}")
            
        chat_history = "\n".join(prompt_lines)
        
        print("\n=== 📝 Recent Chat History ===")
        print(chat_history)
        print("=============================\n")

        # 3. 构建 System Instruction
        system_instruction = (
            "你是一位专业的自闭症 (ASD) 特教 AI 助教。你的任务是阅读家校群聊记录，"
            "分析儿童（小明）的干预进度，并基于 FSRS (Free Spaced Repetition Scheduler) "
            "算法思想，为家长推荐下一个阶段的干预卡片配置。"
        )

        prompt = (
            f"以下是最近的家校沟通记录：\n{chat_history}\n\n"
            "请根据上述记录进行分析，并输出 JSON 格式的推荐配置。包含对当前进度的分析总结、"
            "推荐的干预主题和卡片类型、难度等级(1-5)，以及你想发送到群聊里的回复消息。"
        )
        
        # 4 & 5. 调用 Gemini 思考 (Think) 并使用结构化输出
        print("🧠 Thinking with Gemini-2.5-pro...")
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
            
            # 解析模型返回的 JSON
            response_json = response.text
            print(f"\n✨ Gemini Response JSON:\n{response_json}\n")
            
            # Pydantic 校验与转对象
            ai_output = AICardResponse.model_validate_json(response_json)
            
        except Exception as e:
            print(f"❌ Error calling Gemini API: {e}")
            import traceback
            traceback.print_exc()
            return
            
        # 格式化最终落库的消息内容
        final_content = (
            f"{ai_output.ai_message}\n\n"
            f"【🤖 AI 智能干预配置建议】\n"
            f"📝 分析总结: {ai_output.analysis}\n"
            f"🏷️ 卡片类型: {ai_output.card_type}\n"
            f"🎯 推荐主题: {ai_output.topic}\n"
            f"⭐ 难度级别: L{ai_output.difficulty}"
        )

        # 获取超级助教 (AGENT) 的 ID
        agent_stmt = select(User).where(User.role == RoleEnum.AGENT).limit(1)
        agent_result = await session.execute(agent_stmt)
        agent_user = agent_result.scalar_one_or_none()
        
        if agent_user:
            agent_id = agent_user.id
            print(f"🔍 Found AGENT user, using ID: {agent_id}")
        else:
            # 兜底：寻找 ID 为 3 的用户或其他用户
            check_3_stmt = select(User.id).where(User.id == 3)
            if await session.scalar(check_3_stmt):
                agent_id = 3
                print(f"⚠️ AGENT user not found, falling back to ID: {agent_id}")
            else:
                fallback_stmt = select(User.id).limit(1)
                agent_id = await session.scalar(fallback_stmt)
                print(f"⚠️ AGENT user and ID=3 not found, falling back to ID: {agent_id}")
                
            if not agent_id:
                print("❌ No user found in the database for fallback. Exiting.")
                return
        
        # 6. 落库回复 (Write)
        new_log = IepCommunicationLog(
            child_id=child_id,
            sender_id=agent_id,
            content=final_content
        )
        
        session.add(new_log)
        await session.commit()
        
        print("✅ Agent job finished successfully. Real AI log inserted.")

if __name__ == '__main__':
    asyncio.run(run_agent_job())
