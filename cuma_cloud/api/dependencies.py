"""FastAPI dependency injection for authentication and ABAC authorization."""

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import jwt
from jwt import PyJWTError

from cuma_cloud.core.config import settings
from cuma_cloud.core.database import get_db
from cuma_cloud.models import CloudAccount, ChildProfile, RoleEnum, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> CloudAccount:
    """
    Decode JWT, extract user identity, and return the CloudAccount.

    Raises:
        HTTPException 401: Invalid token or user not found.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
        )
        sub: Optional[str] = payload.get("sub")
        if sub is None:
            raise credentials_exception
    except PyJWTError:
        raise credentials_exception

    result = await db.execute(select(CloudAccount).where(CloudAccount.email == sub))
    account = result.scalar_one_or_none()
    if account is None:
        raise credentials_exception
    return account


# ---------------------------------------------------------------------------
# 4A 架构 - ABAC 鉴权依赖（Policy as Code）
# ---------------------------------------------------------------------------


async def get_current_user_abac(db: AsyncSession = Depends(get_db)) -> User:
    """
    Mock：直接从数据库查询 id=1 的 User 作为当前用户。
    后续可替换为 JWT 解析后按 cloud_account_id 关联 User。
    """
    result = await db.execute(select(User).where(User.id == 1))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="当前用户不存在（请确保 users 表中有 id=1 的记录）",
        )
    return user


async def verify_child_access(
    child_id: int,
    current_user: User = Depends(get_current_user_abac),
    db: AsyncSession = Depends(get_db),
) -> ChildProfile:
    """
    ABAC 策略：根据当前用户角色与 child 的三元组 (institution, teacher, parent) 判定访问权限。
    - PARENT: 仅当 child.parent_id == current_user.id
    - TEACHER: child.institution_id == current_user.institution_id 且 assigned_teacher_id == current_user.id
    - QCQ_ADMIN: child.institution_id == current_user.institution_id
    - AGENT: 直接放行
    """
    result = await db.execute(select(ChildProfile).where(ChildProfile.id == child_id))
    child = result.scalar_one_or_none()
    if child is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="儿童档案不存在")

    if current_user.role == RoleEnum.AGENT:
        return child

    if current_user.role == RoleEnum.PARENT:
        if child.parent_id == current_user.id:
            return child
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该儿童档案")

    if current_user.role == RoleEnum.TEACHER:
        if (
            child.institution_id == current_user.institution_id
            and child.assigned_teacher_id == current_user.id
        ):
            return child
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该儿童档案")

    if current_user.role == RoleEnum.QCQ_ADMIN:
        if child.institution_id == current_user.institution_id:
            return child
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该儿童档案")

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="未知角色，无权访问")
