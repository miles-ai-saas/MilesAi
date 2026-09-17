"""运营端风控 DTO：风险事件、黑名单与限流规则。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from miles_admin.app_ops.schemas.enums import RiskSeverity


# 风险事件输出。
class RiskEventOut(BaseModel):
    id: UUID = Field(description="风险事件 ID")
    event_type: str = Field(description="事件类型")
    severity: RiskSeverity = Field(description="严重级别")
    tenant_id: UUID | None = Field(description="关联租户 ID")
    user_id: UUID | None = Field(description="关联用户 ID")
    ip_address: str | None = Field(description="来源 IP 地址")
    detail: dict = Field(description="事件详情（JSON）")
    is_resolved: bool = Field(description="是否已处理")
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}


# 新增 IP 黑名单入参。
class IpBlacklistCreate(BaseModel):
    ip_address: str = Field(description="IP 地址")
    reason: str | None = Field(None, description="封禁原因")


# IP 黑名单输出。
class IpBlacklistOut(BaseModel):
    id: UUID = Field(description="黑名单记录 ID")
    ip_address: str = Field(description="IP 地址")
    reason: str | None = Field(description="封禁原因")
    is_active: bool = Field(description="是否生效")
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}


# 创建限流规则入参。
class RateLimitRuleCreate(BaseModel):
    name: str = Field(description="规则名称")
    path_pattern: str = Field(description="路径匹配模式")
    limit_per_minute: int = Field(60, ge=1, le=10000, description="每分钟请求上限")
    description: str | None = Field(None, description="规则描述")


# 更新限流规则入参（仅传需变更字段）。
class RateLimitRuleUpdate(BaseModel):
    name: str | None = Field(None, description="规则名称")
    path_pattern: str | None = Field(None, description="路径匹配模式")
    limit_per_minute: int | None = Field(None, ge=1, le=10000, description="每分钟请求上限")
    is_active: bool | None = Field(None, description="是否启用")
    description: str | None = Field(None, description="规则描述")


# 限流规则输出。
class RateLimitRuleOut(BaseModel):
    id: UUID = Field(description="限流规则 ID")
    name: str = Field(description="规则名称")
    path_pattern: str = Field(description="路径匹配模式")
    limit_per_minute: int = Field(description="每分钟请求上限")
    is_active: bool = Field(description="是否启用")
    description: str | None = Field(description="规则描述")

    model_config = {"from_attributes": True}
