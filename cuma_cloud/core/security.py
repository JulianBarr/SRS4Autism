"""Security utilities: password hashing and JWT token generation."""

from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt

from cuma_cloud.core.config import settings

# Default token expiration: 7 days (local-first desktop app)
DEFAULT_ACCESS_TOKEN_EXPIRE_DAYS = 7


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT access token.

    Args:
        data: Payload dict (e.g. {"sub": email}).
        expires_delta: Optional custom expiration. Defaults to 7 days.

    Returns:
        Encoded JWT string.
    """
    to_encode = data.copy()
    if expires_delta is not None:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=DEFAULT_ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode["exp"] = expire
    to_encode["iat"] = datetime.now(timezone.utc)
    return jwt.encode(
        to_encode,
        settings.jwt_secret,
        algorithm="HS256",
    )
