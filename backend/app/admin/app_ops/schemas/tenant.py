from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.platform.tenant import TenantStatus


class AdminTenantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, description="租户名称")
    description: str | None = Field(None, description="租户描述")
    plan_id: UUID | None = Field(None, description="计费方案 ID")
    status: TenantStatus = Field(default=TenantStatus.ACTIVE, description="租户状态")


class AdminTenantUpdate(BaseModel):
    name: str | None = Field(None, description="租户名称")
    description: str | None = Field(None, description="租户描述")
    plan_id: UUID | None = Field(None, description="计费方案 ID")
    status: TenantStatus | None = Field(None, description="租户状态")
    is_active: bool | None = Field(None, description="是否启用")
    max_knowledge_bases: int | None = Field(None, description="知识库数量上限")
    max_storage_mb: int | None = Field(None, description="存储空间上限（MB）")
    max_tokens_monthly: int | None = Field(None, description="每月 Token 用量上限")
    max_agents: int | None = Field(None, description="智能体数量上限")
    max_flows: int | None = Field(None, description="工作流数量上限")


class AdminTenantOut(BaseModel):
    id: UUID = Field(description="租户 ID")
    name: str = Field(description="租户名称")
    description: str | None = Field(description="租户描述")
    is_active: bool = Field(description="是否启用")
    status: TenantStatus = Field(description="租户状态")
    plan_id: UUID | None = Field(description="计费方案 ID")
    plan_name: str | None = Field(None, description="计费方案名称")
    max_knowledge_bases: int = Field(description="知识库数量上限")
    max_storage_mb: int = Field(description="存储空间上限（MB）")
    max_tokens_monthly: int = Field(description="每月 Token 用量上限")
    max_agents: int = Field(description="智能体数量上限")
    max_flows: int = Field(description="工作流数量上限")
    tokens_used_month: int = Field(description="本月已用 Token 数")
    storage_used_mb: int = Field(description="已用存储空间（MB）")
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}


class TenantUsageStats(BaseModel):
    knowledge_bases: int = Field(0, description="知识库数量")
    documents: int = Field(0, description="文档数量")
    agents: int = Field(0, description="智能体数量")
    flows: int = Field(0, description="工作流数量")
    users: int = Field(0, description="用户数量")
    storage_used_mb: int = Field(0, description="已用存储空间（MB）")
    tokens_used_month: int = Field(0, description="本月已用 Token 数")


class AdminTenantDetail(AdminTenantOut):
    usage: TenantUsageStats = Field(description="资源使用统计")


class TenantQuotaUpdate(BaseModel):
    max_tokens_monthly: int | None = Field(None, description="每月 Token 用量上限")
    max_storage_mb: int | None = Field(None, description="存储空间上限（MB）")
    max_knowledge_bases: int | None = Field(None, description="知识库数量上限")
    max_agents: int | None = Field(None, description="智能体数量上限")
    max_flows: int | None = Field(None, description="工作流数量上限")
    tokens_used_month: int | None = Field(None, description="本月已用 Token 数")
    storage_used_mb: int | None = Field(None, description="已用存储空间（MB）")
