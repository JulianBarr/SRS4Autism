from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from cuma_cloud.core.database import get_db
from cuma_cloud.api.dependencies import get_current_user_abac
from cuma_cloud.models import User, Institution, InstitutionStatusEnum

router = APIRouter(prefix="/users", tags=["users"])

class JoinInstitutionRequest(BaseModel):
    institution_id: int

@router.post("/me/institution")
async def join_institution(
    req: JoinInstitutionRequest,
    current_user: User = Depends(get_current_user_abac),
    db: AsyncSession = Depends(get_db)
):
    """Teacher requests to join an institution."""
    # Verify institution exists
    inst = await db.scalar(select(Institution).where(Institution.id == req.institution_id))
    if not inst:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Institution not found"
        )
    
    current_user.institution_id = req.institution_id
    current_user.institution_status = InstitutionStatusEnum.PENDING
    
    await db.commit()
    await db.refresh(current_user)
    
    return {
        "status": "success",
        "message": f"Requested to join {inst.name}. Pending approval."
    }
