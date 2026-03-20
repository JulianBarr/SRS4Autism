import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# 引入 models 和 database 组件
from cuma_cloud.models import Base, Institution, User, ChildProfile, RoleEnum
from cuma_cloud.core.database import engine, async_sessionmaker_factory
from cuma_cloud.core.security import get_password_hash

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def seed_data():
    """
    初始化数据库并插入 ABAC 模型的 Mock 数据。
    """
    logger.info("开始初始化数据库表...")
    async with engine.begin() as conn:
        # 🌟 关键优化：先彻底删表，再重建，确保序列重置，小明必定是 id=1
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    logger.info("数据库表创建完成。")

    default_hashed_password = get_password_hash("cuma123")

    logger.info("开始插入 Mock 数据...")
    async with async_sessionmaker_factory() as session:
        # 1. 创建 Institution: QCQ机构
        qcq_inst = Institution(id=1, name="QCQ机构")
        session.add(qcq_inst)
        await session.flush()  # 获取 qcq_inst.id
        
        # 2. 创建 User (Teacher): teacher_a@qcq.com
        teacher_a = User(
            id=1,  # 强制 id=1 匹配 mock 鉴权
            email="teacher_a@qcq.com",
            hashed_password=default_hashed_password,
            role=RoleEnum.TEACHER,
            institution_id=qcq_inst.id
        )
        session.add(teacher_a)
        
        # 3. 创建 User (Parent): parent_b@test.com
        parent_b = User(
            id=2,  # 强制 id=2
            email="parent_b@test.com",
            hashed_password=default_hashed_password,
            role=RoleEnum.PARENT
        )
        session.add(parent_b)

        # 🌟 4. 新增：创建 User (Agent): 超级助教 AI
        agent_ai = User(
            id=3,  # 强制 id=3，完美对接前端 UI 的 {"x-mock-user-id": "3"}
            email="ai@cuma.com",
            hashed_password=default_hashed_password,
            role=RoleEnum.AGENT,
            institution_id=qcq_inst.id
        )
        session.add(agent_ai)

        await session.flush() 
        
        # 5. 创建 Child A (归属 Teacher A): 小明 (数据库重建后，id必然为1)
        child_ming = ChildProfile(
            name="小明",
            institution_id=qcq_inst.id,
            assigned_teacher_id=teacher_a.id
        )
        session.add(child_ming)

        # 🌟 抢救周一鸣：在真实数据库里给他建档，并分配给 Teacher A
        child_yiming = ChildProfile(
            name="Zhou Yiming (周一鸣）",
            institution_id=qcq_inst.id,
            assigned_teacher_id=teacher_a.id
        )
        session.add(child_yiming)

        # 🌟 顺手把 David Shannon 也抢救回来，保持队形完整
        child_david = ChildProfile(
            name="David Shannon",
            institution_id=qcq_inst.id,
            assigned_teacher_id=teacher_a.id
        )
        session.add(child_david)
        
        # 6. 创建 Child B (归属 Parent B): 小红
        child_hong = ChildProfile(
            name="小红",
            parent_id=parent_b.id
        )
        session.add(child_hong)
        
        # 7. 创建 Child C (归属其他老师): 小刚
        child_gang = ChildProfile(
            name="小刚",
            institution_id=qcq_inst.id
            # 不关联给 Teacher A
        )
        session.add(child_gang)
        
        # 提交事务
        await session.commit()
        logger.info("Mock 数据插入成功！(包含 AI Agent 账号和全部测试儿童)")

if __name__ == "__main__":
    asyncio.run(seed_data())
