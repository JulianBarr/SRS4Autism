"""儿童档案路由：受 ABAC 保护的资源访问。"""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cuma_cloud.api.dependencies import (
    get_authorized_child,
    get_current_user_abac,
    verify_child_access,
)
from cuma_cloud.core.database import get_db
from cuma_cloud.models import ChildProfile, RoleEnum, User

router = APIRouter(tags=["Children"])


@router.get("/children/me")
async def get_my_children(
    current_user: User = Depends(get_current_user_abac),
    db: AsyncSession = Depends(get_db),
) -> List[dict]:
    """
    根据当前用户的角色获取儿童列表。
    - TEACHER: 获取 assigned_teacher_id 为当前用户的儿童
    - PARENT: 获取 parent_id 为当前用户的儿童
    - QCQ_ADMIN: 获取同机构的所有儿童
    - AGENT: 获取所有儿童
    """
    query = select(ChildProfile)
    
    if current_user.role == RoleEnum.TEACHER:
        query = query.where(ChildProfile.assigned_teacher_id == current_user.id)
    elif current_user.role == RoleEnum.PARENT:
        query = query.where(ChildProfile.parent_id == current_user.id)
    elif current_user.role == RoleEnum.QCQ_ADMIN:
        query = query.where(ChildProfile.institution_id == current_user.institution_id)
    # AGENT 可以看所有
    
    result = await db.execute(query)
    children = result.scalars().all()
    
    return [{"id": child.id, "name": child.name} for child in children]


@router.get("/children/{child_id}")
async def get_child(child: ChildProfile = Depends(verify_child_access)) -> dict:
    """
    获取儿童档案（id、name）。
    通过 verify_child_access 注入，鉴权通过后返回。
    """
    return {"id": child.id, "name": child.name}


@router.get("/test-auth/{child_id}")
async def test_child_access(child: ChildProfile = Depends(get_authorized_child)) -> dict:
    """
    Temporary test endpoint to verify RBAC data isolation via get_authorized_child.
    If the request passes the dependency, the caller is allowed to access that child.
    """
    return {
        "status": "success",
        "message": "Access Granted! 🛡️",
        "authorized_child_name": child.name,
        "parent_id": child.parent_id,
    }
