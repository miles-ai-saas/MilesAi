from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.tenant import TenantStatus


class AdminTenantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    plan_id: UUID | None = None
    status: TenantStatus = TenantStatus.ACTIVE


class AdminTenantUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    plan_id: UUID | None = None
    status: TenantStatus | None = None
    is_active: bool | None = None
    max_knowledge_bases: int | None = None
    max_storage_mb: int | None = None
    max_tokens_monthly: int | None = None
    max_agents: int | None = None
    max_flows: int | None = None


class AdminTenantOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    is_active: bool
    status: TenantStatus
    plan_id: UUID | None
    plan_name: str | None = None
    max_knowledge_bases: int
    max_storage_mb: int
    max_tokens_monthly: int
    max_agents: int
    max_flows: int
    tokens_used_month: int
    storage_used_mb: int
    created_at: datetime

    model_config = {"from_attributes": True}


class TenantUsageStats(BaseModel):
    knowledge_bases: int = 0
    documents: int = 0
    agents: int = 0
    flows: int = 0
    users: int = 0
    storage_used_mb: int = 0
    tokens_used_month: int = 0


class AdminTenantDetail(AdminTenantOut):
    usage: TenantUsageStats


class TenantQuotaUpdate(BaseModel):
    max_tokens_monthly: int | None = None
    max_storage_mb: int | None = None
    max_knowledge_bases: int | None = None
    max_agents: int | None = None
    max_flows: int | None = None
    tokens_used_month: int | None = None
    storage_used_mb: int | None = None
