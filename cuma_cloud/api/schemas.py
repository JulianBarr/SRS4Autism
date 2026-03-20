"""Pydantic schemas for Cuma Cloud API."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


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


# --- ABAC Policy Schemas (Phase 3: Distributed Authorization) ---


class ABACRuleDetail(BaseModel):
    """Schema for the rules JSONB payload within an ABAC policy."""

    allowed_actions: list[str] = Field(
        ...,
        description="Actions permitted on the resource (e.g. read, write, sync)",
    )
    conditions: dict[str, Any] = Field(
        default_factory=dict,
        description="Attribute conditions (e.g. is_assigned_therapist: true)",
    )


class ABACPolicyCreate(BaseModel):
    """Schema for creating a new ABAC policy."""

    institution_id: Optional[str] = None
    policy_name: str
    resource_type: str
    rules: ABACRuleDetail
    version: int = 1


class ABACPolicyResponse(BaseModel):
    """Schema for ABAC policy response."""

    id: int
    account_id: int
    institution_id: Optional[str] = None
    policy_name: str
    resource_type: str
    rules: ABACRuleDetail
    version: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Telemetry Sync Schemas (Phase 4: Auditing & Telemetry) ---


class TelemetrySyncRequest(BaseModel):
    """Schema for batched telemetry sync from Local-First clients."""

    client_device_id: str = Field(..., description="Device identifier (e.g. ipad-pro-living-room)")
    payload: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Batched logs from local SQLite (FSRS reviews, usage metrics, etc.)",
    )


class TelemetrySyncResponse(BaseModel):
    """Schema for telemetry sync acknowledgment."""

    id: int
    synced_at: datetime
    status: str = "success"

    model_config = ConfigDict(from_attributes=True)


# --- IEP Communication Schemas ---

class IepLogCreate(BaseModel):
    content: str

class IepLogResponse(BaseModel):
    id: int
    child_id: int
    sender_id: int
    content: str
    created_at: datetime
    
    # Nested info optionally
    sender_role: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)
