import asyncio
import os
import sys

# Add project root to sys.path so we can import cuma_cloud
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from cuma_cloud.core.database import async_sessionmaker_factory
from cuma_cloud.models import IepCommunicationLog, RoleEnum, User, ChildProfile

async def run_agent_job(child_id: int = 1):
    print(f"Starting agent job for child {child_id}...")
    
    async with async_sessionmaker_factory() as session:
        # 验证 child_id 是否存在，如果不存在且只是测试，可以选择使用第一个 child
        child_stmt = select(ChildProfile.id).where(ChildProfile.id == child_id)
        child_result = await session.execute(child_stmt)
        if not child_result.scalar_one_or_none():
            print(f"Child {child_id} not found. Attempting to fallback to first available child...")
            fallback_child_stmt = select(ChildProfile.id).limit(1)
            fallback_child_result = await session.execute(fallback_child_stmt)
            child_id = fallback_child_result.scalar_one_or_none()
            if not child_id:
                print("No children found in the database. Exiting.")
                return
            print(f"Using fallback child_id: {child_id}")
            
        # 1. 获取上下文：查询 child_id 的所有沟通记录，关联 sender，按时间正序
        stmt = (
            select(IepCommunicationLog)
            .where(IepCommunicationLog.child_id == child_id)
            .options(selectinload(IepCommunicationLog.sender))
            .order_by(IepCommunicationLog.created_at.asc())
        )
        result = await session.execute(stmt)
        logs = result.scalars().all()
        
        # if not logs:
        #     print(f"No IEP communication logs found for child {child_id}.")
        #     return

        # 2. 构建 Prompt
        prompt_lines = [
            "你是一个专业的自闭症干预 AI 助教。请阅读以下家长和老师的沟通记录，并提取干预进度：\n"
        ]
        
        for log in logs:
            sender_role = log.sender.role.value if log.sender and log.sender.role else "unknown"
            time_str = log.created_at.strftime("%Y-%m-%d %H:%M:%S") if log.created_at else "未知时间"
            prompt_lines.append(f"[{time_str}] {sender_role}: {log.content}")
            
        prompt = "\n".join(prompt_lines)
        
        # 4. 打印拼装好的 Prompt
        print("=== 拼装好的 Prompt ===")
        print(prompt)
        print("=======================\n")
        
        # 3. 模拟大模型响应与落库
        mock_ai_response = (
            "检测到小明已掌握颜色区分。正在为您生成【红蓝积木分拣游戏】的 FSRS 卡片配置：\n"
            '{"card_type": "FSRS", "topic": "红蓝积木", "difficulty": 1}'
        )
        
        # 查找 role 为 AGENT 的用户ID
        agent_stmt = select(User).where(User.role == RoleEnum.AGENT).limit(1)
        agent_result = await session.execute(agent_stmt)
        agent_user = agent_result.scalar_one_or_none()
        
        if agent_user:
            agent_id = agent_user.id
            print(f"Found AGENT user, using ID: {agent_id}")
        else:
            # 根据要求，如果没有找到 role 为 AGENT 的用户，兜底硬编码为 3
            # 为了防止外键报错，先检查 3 是否存在
            check_3_stmt = select(User.id).where(User.id == 3)
            if await session.scalar(check_3_stmt):
                agent_id = 3
                print(f"AGENT user not found, falling back to ID: {agent_id}")
            else:
                fallback_stmt = select(User.id).limit(1)
                agent_id = await session.scalar(fallback_stmt)
                print(f"AGENT user and ID=3 not found, falling back to any available user ID: {agent_id}")
                
            if not agent_id:
                print("No user found in the database for fallback. Exiting.")
                return
        
        # 创建新的沟通记录
        new_log = IepCommunicationLog(
            child_id=child_id,
            sender_id=agent_id,
            content=mock_ai_response
        )
        
        session.add(new_log)
        await session.commit()
        
        print("✅ Agent job finished successfully. New mock AI log inserted.")

if __name__ == '__main__':
    asyncio.run(run_agent_job())
