"""FastAPI dependency injection for authentication."""

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import jwt
from jwt import PyJWTError

from cuma_cloud.core.config import settings
from cuma_cloud.core.database import get_db
from cuma_cloud.models import CloudAccount

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
