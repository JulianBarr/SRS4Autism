"""ABAC policy distribution routes. Cloud defines rules; clients pull and enforce offline."""

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from cuma_cloud.api.dependencies import get_current_user
from cuma_cloud.api.schemas import ABACPolicyCreate, ABACPolicyResponse
from cuma_cloud.core.database import get_db
from cuma_cloud.models import ABACPolicy, CloudAccount

router = APIRouter(tags=["Authorization Policies"])


@router.post("", response_model=ABACPolicyResponse)
async def create_policy(
    body: ABACPolicyCreate,
    current_user: CloudAccount = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ABACPolicy:
    """
    Create a new ABAC policy (Admin/Internal tool).

    The policy is stored with the current user as creator (account_id).
    """
    policy = ABACPolicy(
        account_id=current_user.id,
        institution_id=body.institution_id,
        policy_name=body.policy_name,
        resource_type=body.resource_type,
        rules=body.rules.model_dump(),
        version=body.version,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return policy


@router.get("", response_model=list[ABACPolicyResponse])
async def list_policies(
    current_user: CloudAccount = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ABACPolicy]:
    """
    List ABAC policies available to the current user.

    Returns policies where:
    - institution_id matches the user's institution_id, OR
    - institution_id is None (global default policies).
    """
    user_inst = current_user.institution_id
    stmt = select(ABACPolicy).where(
        or_(
            ABACPolicy.institution_id == user_inst,
            ABACPolicy.institution_id.is_(None),
        )
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
