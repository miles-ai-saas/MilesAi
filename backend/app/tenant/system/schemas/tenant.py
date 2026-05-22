from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.tenant import TenantStatus


class TenantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    max_knowledge_bases: int = 10
    max_storage_mb: int = 10240


class TenantUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    max_knowledge_bases: int | None = None
    max_storage_mb: int | None = None


class TenantOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    is_active: bool
    max_knowledge_bases: int
    max_storage_mb: int
    plan_id: UUID | None = None
    status: TenantStatus = TenantStatus.ACTIVE
    max_tokens_monthly: int = 1_000_000
    max_agents: int = 20
    max_flows: int = 20
    tokens_used_month: int = 0
    storage_used_mb: int = 0
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
