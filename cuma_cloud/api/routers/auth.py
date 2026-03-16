"""Authentication routes: login and register."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cuma_cloud.api.schemas import CloudAccountCreate, CloudAccountResponse, TokenResponse
from cuma_cloud.core.database import get_db
from cuma_cloud.core.security import create_access_token, get_password_hash, verify_password
from cuma_cloud.models import CloudAccount

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
    result = await db.execute(select(CloudAccount).where(CloudAccount.email == form_data.username))
    account = result.scalar_one_or_none()
    if account is None or not verify_password(form_data.password, account.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(data={"sub": account.email})
    return {"access_token": token, "token_type": "bearer"}


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
