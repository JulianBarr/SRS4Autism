import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# 引入 models 和 database 组件
from cuma_cloud.models import Base, Institution, User, ChildProfile, RoleEnum
from cuma_cloud.core.database import engine, async_sessionmaker_factory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def seed_data():
    """
    初始化数据库并插入 ABAC 模型的 Mock 数据。
    """
    logger.info("开始初始化数据库表...")
    # 使用 Base.metadata.create_all 创建表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("数据库表创建完成。")

    logger.info("开始插入 Mock 数据...")
    async with async_sessionmaker_factory() as session:
        # 清理已有数据，防止重复执行报错
        await session.execute(text("TRUNCATE TABLE child_profiles, users, institutions CASCADE"))
        
        # 1. 创建 Institution: QCQ机构
        qcq_inst = Institution(id=1, name="QCQ机构")
        session.add(qcq_inst)
        await session.flush()  # 获取 qcq_inst.id
        
        # 2. 创建 User (Teacher): teacher_a@qcq.com
        teacher_a = User(
            id=1,  # 强制 id=1 匹配 mock 鉴权
            email="teacher_a@qcq.com",
            role=RoleEnum.TEACHER,
            institution_id=qcq_inst.id
        )
        session.add(teacher_a)
        
        # 3. 创建 User (Parent): parent_b@test.com
        parent_b = User(
            id=2,  # 强制 id=2 避免序列冲突
            email="parent_b@test.com",
            role=RoleEnum.PARENT
        )
        session.add(parent_b)
        await session.flush()  # 获取 teacher_a.id 和 parent_b.id
        
        # 4. 创建 Child B (归属 Teacher A): 小明
        child_ming = ChildProfile(
            name="小明",
            institution_id=qcq_inst.id,
            assigned_teacher_id=teacher_a.id
        )
        session.add(child_ming)
        
        # 5. 创建 Child C (归属 Parent B): 小红
        child_hong = ChildProfile(
            name="小红",
            parent_id=parent_b.id
        )
        session.add(child_hong)
        
        # 6. 创建 Child D (归属其他老师): 小刚
        child_gang = ChildProfile(
            name="小刚",
            institution_id=qcq_inst.id
            # 不关联给 Teacher A
        )
        session.add(child_gang)
        
        # 提交事务
        await session.commit()
        logger.info("Mock 数据插入成功！")

if __name__ == "__main__":
    asyncio.run(seed_data())
