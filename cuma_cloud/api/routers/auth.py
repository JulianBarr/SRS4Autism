"""Authentication routes: login and register."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cuma_cloud.api.schemas import CloudAccountCreate, CloudAccountResponse, TokenResponse
from cuma_cloud.core.database import get_db
from cuma_cloud.core.security import create_access_token, get_password_hash, verify_password
from cuma_cloud.models import CloudAccount, User

router = APIRouter(tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    OAuth2-compatible token login.

    Use `username` as email and `password` as password.
    Swagger UI will show the standard OAuth2 form.
    """
    # 查找 User 表（Teacher / Parent / Agent 等角色）
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()
    
    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # sub = cloud User.id; role = ABAC role (local engine 8000 reads both for RBAC)
    token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value},
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "institution_id": user.institution_id,
            "institution_status": user.institution_status
        }
    }


@router.post("/register", response_model=CloudAccountResponse)
async def register(
    body: CloudAccountCreate,
    db: AsyncSession = Depends(get_db),
) -> CloudAccount:
    """
    Register a new account (internal/admin utility).

    Raises 400 if email already exists.
    """
    result = await db.execute(select(CloudAccount).where(CloudAccount.email == body.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    new_account = CloudAccount(
        email=body.email,
        hashed_password=get_password_hash(body.password),
    )
    db.add(new_account)
    await db.commit()
    await db.refresh(new_account)
    return new_account
