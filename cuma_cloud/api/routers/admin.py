from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cuma_cloud.core.database import get_db
from cuma_cloud.api.dependencies import get_current_user_abac
from cuma_cloud.models import User, ChildProfile, RoleEnum, InstitutionStatusEnum

router = APIRouter(prefix="/admin", tags=["admin"])

# Schemas
class TeacherResponse(BaseModel):
    id: int
    name: str
    username: str
    role: str
    institution_status: Optional[InstitutionStatusEnum] = None
    
    class Config:
        from_attributes = True

class ChildResponse(BaseModel):
    id: int
    name: str
    assigned_teacher_id: Optional[int] = None
    
    class Config:
        from_attributes = True

class AssignRequest(BaseModel):
    user_id: int
    child_id: int


def verify_admin(current_user: User = Depends(get_current_user_abac)):
    """Verify that the current user has admin privileges."""
    if current_user.role != RoleEnum.QCQ_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires admin privileges"
        )
    return current_user


@router.get("/teachers", response_model=List[TeacherResponse])
async def get_teachers(
    admin_user: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all teachers in the same institution."""
    query = select(User).where(
        User.role == RoleEnum.TEACHER,
        User.institution_id == admin_user.institution_id,
        User.institution_status == InstitutionStatusEnum.APPROVED
    )
    result = await db.execute(query)
    teachers = result.scalars().all()
    # Map email to name and username for the frontend
    return [{"id": t.id, "name": t.email, "username": t.email, "role": t.role.value, "institution_status": t.institution_status} for t in teachers]


@router.get("/pending_teachers", response_model=List[TeacherResponse])
async def get_pending_teachers(
    admin_user: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get pending teachers for the admin's institution."""
    query = select(User).where(
        User.role == RoleEnum.TEACHER,
        User.institution_id == admin_user.institution_id,
        User.institution_status == InstitutionStatusEnum.PENDING
    )
    result = await db.execute(query)
    teachers = result.scalars().all()
    return [{"id": t.id, "name": t.email, "username": t.email, "role": t.role.value, "institution_status": t.institution_status} for t in teachers]


@router.post("/teachers/{user_id}/approve")
async def approve_teacher(
    user_id: int,
    admin_user: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db)
):
    """Approve a pending teacher."""
    teacher = await db.scalar(
        select(User).where(
            User.id == user_id,
            User.institution_id == admin_user.institution_id,
            User.institution_status == InstitutionStatusEnum.PENDING
        )
    )
    if not teacher:
        raise HTTPException(status_code=404, detail="Pending teacher not found")
        
    teacher.institution_status = InstitutionStatusEnum.APPROVED
    await db.commit()
    return {"status": "success", "message": f"Teacher {teacher.email} approved"}


@router.post("/teachers/{user_id}/reject")
async def reject_teacher(
    user_id: int,
    admin_user: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db)
):
    """Reject a pending teacher."""
    teacher = await db.scalar(
        select(User).where(
            User.id == user_id,
            User.institution_id == admin_user.institution_id,
            User.institution_status == InstitutionStatusEnum.PENDING
        )
    )
    if not teacher:
        raise HTTPException(status_code=404, detail="Pending teacher not found")
        
    teacher.institution_status = None
    teacher.institution_id = None
    await db.commit()
    return {"status": "success", "message": f"Teacher {teacher.email} rejected"}


@router.get("/children", response_model=List[ChildResponse])
async def get_children(
    admin_user: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all children in the same institution."""
    query = select(ChildProfile).where(
        ChildProfile.institution_id == admin_user.institution_id
    )
    result = await db.execute(query)
    children = result.scalars().all()
    return children


@router.post("/assign")
async def assign_child_to_teacher(
    req: AssignRequest,
    admin_user: User = Depends(verify_admin),
    db: AsyncSession = Depends(get_db)
):
    """Assign a child to a teacher."""
    # Verify the teacher exists and belongs to the same institution
    teacher = await db.scalar(
        select(User).where(
            User.id == req.user_id,
            User.role == RoleEnum.TEACHER,
            User.institution_id == admin_user.institution_id
        )
    )
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found in your institution")
        
    # Verify the child exists and belongs to the same institution
    child = await db.scalar(
        select(ChildProfile).where(
            ChildProfile.id == req.child_id,
            ChildProfile.institution_id == admin_user.institution_id
        )
    )
    if not child:
        raise HTTPException(status_code=404, detail="Child not found in your institution")
        
    # Option 1: Update the direct foreign key which ABAC uses natively
    child.assigned_teacher_id = teacher.id
    
    await db.commit()
    
    return {"status": "success", "message": f"Child {child.name} assigned to teacher {teacher.email}"}
