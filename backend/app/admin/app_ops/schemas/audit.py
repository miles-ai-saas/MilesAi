from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AuditLogOut(BaseModel):
    id: UUID = Field(description="审计日志 ID")
    admin_id: UUID | None = Field(description="操作管理员 ID")
    tenant_id: UUID | None = Field(description="关联租户 ID")
    action: str = Field(description="操作动作")
    resource_type: str | None = Field(description="资源类型")
    resource_id: str | None = Field(description="资源 ID")
    ip_address: str | None = Field(description="客户端 IP 地址")
    detail: dict = Field(description="操作详情（JSON）")
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}
