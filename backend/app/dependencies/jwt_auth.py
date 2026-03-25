"""
JWT validation for local engine (port 8000).

Must use the same secret and algorithm as cuma_cloud (HS256, env JWT_SECRET).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import PyJWTError

# Align with cuma_cloud/core/security.py and cuma_cloud/core/config.py (jwt_secret → JWT_SECRET)
_DEFAULT_JWT_SECRET_PLACEHOLDER = (
    "CHANGE_ME_SET_JWT_SECRET_TO_MATCH_CUMA_CLOUD__DO_NOT_USE_IN_PROD"
)
JWT_SECRET = os.environ.get("JWT_SECRET", _DEFAULT_JWT_SECRET_PLACEHOLDER)
JWT_ALGORITHM = "HS256"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


@dataclass(frozen=True)
class TokenUser:
    """Identity extracted from a validated cloud-issued JWT."""

    user_id: int
    role: str


def get_current_user_from_token(
    token: str = Depends(oauth2_scheme),
) -> TokenUser:
    """
    Verify Bearer JWT and return ``user_id`` (from ``sub``) and ``role`` claim.

    Raises:
        HTTPException 401: Missing/invalid token, bad ``sub``, or missing ``role``.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
        )
        sub = payload.get("sub")
        if sub is None:
            raise credentials_exception
        user_id = int(sub)
    except (PyJWTError, ValueError, TypeError):
        raise credentials_exception

    role_raw = payload.get("role")
    if role_raw is None or (isinstance(role_raw, str) and not role_raw.strip()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing role claim",
            headers={"WWW-Authenticate": "Bearer"},
        )
    role = str(role_raw).strip().lower()
    return TokenUser(user_id=user_id, role=role)
