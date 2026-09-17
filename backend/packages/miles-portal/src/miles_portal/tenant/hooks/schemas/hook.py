"""钩子定义与绑定的 API 请求/响应模型。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from miles_portal.tenant.hooks.schemas.enums import HookScope, HookTrigger, HookType


# 创建钩子定义；服务层会据此附带一条绑定。
class HookDefinitionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, description="钩子名称")
    hook_type: HookType = Field(default=HookType.HTTP, description="钩子类型")
    config: dict = Field(default_factory=dict, description="钩子配置 JSON")
    trigger: HookTrigger = Field(default=HookTrigger.BEFORE_CALL, description="触发时机")
    scope: HookScope = Field(default=HookScope.GLOBAL, description="作用域")
    target_id: UUID | None = Field(default=None, description="作用域目标 ID（非全局时必填）")
    priority: int = Field(default=100, description="执行优先级（数值越小越优先）")


# 钩子定义可更新字段（名称/配置/启用状态）。
class HookDefinitionUpdate(BaseModel):
    name: str | None = Field(default=None, description="钩子名称")
    config: dict | None = Field(default=None, description="钩子配置 JSON")
    is_active: bool | None = Field(default=None, description="是否启用")


# 钩子定义详情输出。
class HookDefinitionOut(BaseModel):
    id: UUID = Field(description="钩子定义 ID")
    tenant_id: UUID = Field(description="租户 ID")
    name: str = Field(description="钩子名称")
    hook_type: HookType = Field(description="钩子类型")
    config: dict = Field(description="钩子配置 JSON")
    is_active: bool = Field(description="是否启用")
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}


# 为已有钩子新增一条绑定的请求。
class HookBindingCreate(BaseModel):
    scope: HookScope = Field(default=HookScope.GLOBAL, description="作用域")
    target_id: UUID | None = Field(default=None, description="作用域目标 ID")
    trigger: HookTrigger = Field(default=HookTrigger.BEFORE_CALL, description="触发时机")
    priority: int = Field(default=100, description="执行优先级（数值越小越优先）")


# 钩子绑定输出。
class HookBindingOut(BaseModel):
    id: UUID = Field(description="绑定 ID")
    hook_id: UUID = Field(description="钩子定义 ID")
    scope: HookScope = Field(description="作用域")
    target_id: UUID | None = Field(default=None, description="作用域目标 ID")
    trigger: HookTrigger = Field(description="触发时机")
    priority: int = Field(description="执行优先级")
    is_active: bool = Field(description="是否启用")
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}
