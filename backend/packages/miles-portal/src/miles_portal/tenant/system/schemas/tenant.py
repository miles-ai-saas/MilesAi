"""租户主数据请求与响应模型。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from miles_common.schemas.api_enums import TenantStatus


# 创建租户请求。
class TenantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, description="租户名称")
    description: str | None = Field(default=None, description="租户描述")
    max_knowledge_bases: int = Field(default=10, description="知识库数量上限")
    max_storage_mb: int = Field(default=10240, description="存储空间上限（MB）")


# 更新租户请求（配额类字段仅超管可改）。
class TenantUpdate(BaseModel):
    name: str | None = Field(default=None, description="租户名称")
    description: str | None = Field(default=None, description="租户描述")
    is_active: bool | None = Field(default=None, description="是否启用")
    max_knowledge_bases: int | None = Field(default=None, description="知识库数量上限")
    max_storage_mb: int | None = Field(default=None, description="存储空间上限（MB）")


# 租户输出（含配额与本月用量）。
class TenantOut(BaseModel):
    id: UUID = Field(description="租户 ID")
    name: str = Field(description="租户名称")
    description: str | None = Field(default=None, description="租户描述")
    is_active: bool = Field(description="是否启用")
    max_knowledge_bases: int = Field(description="知识库数量上限")
    max_storage_mb: int = Field(description="存储空间上限（MB）")
    plan_id: UUID | None = Field(default=None, description="订阅套餐 ID")
    status: TenantStatus = Field(default=TenantStatus.ACTIVE, description="租户状态")
    max_tokens_monthly: int = Field(default=1_000_000, description="每月 Token 用量上限")
    max_agents: int = Field(default=20, description="智能体数量上限")
    max_flows: int = Field(default=20, description="流程数量上限")
    tokens_used_month: int = Field(default=0, description="本月已用 Token 数")
    storage_used_mb: int = Field(default=0, description="已用存储空间（MB）")
    created_at: datetime | None = Field(default=None, description="创建时间")

    model_config = {"from_attributes": True}
