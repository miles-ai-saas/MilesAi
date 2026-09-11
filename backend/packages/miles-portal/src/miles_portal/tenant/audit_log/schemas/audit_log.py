"""租户审计日志对外输出模型。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# 审计日志输出（含回填的操作用户名）。
class TenantAuditLogOut(BaseModel):
    id: UUID = Field(description="审计日志 ID")
    tenant_id: UUID = Field(description="租户 ID")
    user_id: UUID | None = Field(default=None, description="操作用户 ID")
    username: str | None = Field(default=None, description="操作用户名")
    action: str = Field(description="操作动作")
    resource_type: str | None = Field(default=None, description="资源类型")
    resource_id: str | None = Field(default=None, description="资源 ID")
    ip_address: str | None = Field(default=None, description="客户端 IP")
    detail: dict = Field(description="操作详情 JSON")
    created_at: datetime = Field(description="记录时间")

    model_config = {"from_attributes": True}
