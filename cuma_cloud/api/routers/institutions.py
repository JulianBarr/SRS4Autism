from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from cuma_cloud.core.database import get_db
from cuma_cloud.models import Institution

router = APIRouter(prefix="/institutions", tags=["institutions"])

class InstitutionResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

@router.get("", response_model=List[InstitutionResponse])
async def get_institutions(db: AsyncSession = Depends(get_db)):
    """Get all institutions."""
    result = await db.execute(select(Institution))
    institutions = result.scalars().all()
    
    # Auto seed if empty
    if not institutions:
        seed_inst = Institution(id=1, name="CUMA官方特教中心")
        db.add(seed_inst)
        await db.commit()
        await db.refresh(seed_inst)
        return [seed_inst]
        
    return institutions
