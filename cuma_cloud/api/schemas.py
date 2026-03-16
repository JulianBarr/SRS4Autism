"""Pydantic schemas for Cuma Cloud API."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class CloudAccountCreate(BaseModel):
    """Schema for creating a new cloud account."""

    email: EmailStr
    password: str = Field(..., min_length=8)


class CloudAccountResponse(BaseModel):
    """Schema for cloud account response (excludes hashed_password)."""

    id: int
    email: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """OAuth2 token response schema."""

    access_token: str
    token_type: str = "bearer"
