from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.admin.models import RiskSeverity


class RiskEventOut(BaseModel):
    id: UUID
    event_type: str
    severity: RiskSeverity
    tenant_id: UUID | None
    user_id: UUID | None
    ip_address: str | None
    detail: dict
    is_resolved: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class IpBlacklistCreate(BaseModel):
    ip_address: str
    reason: str | None = None


class IpBlacklistOut(BaseModel):
    id: UUID
    ip_address: str
    reason: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class RateLimitRuleCreate(BaseModel):
    name: str
    path_pattern: str
    limit_per_minute: int = 60
    description: str | None = None


class RateLimitRuleOut(BaseModel):
    id: UUID
    name: str
    path_pattern: str
    limit_per_minute: int
    is_active: bool
    description: str | None

    model_config = {"from_attributes": True}
