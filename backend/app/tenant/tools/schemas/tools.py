"""工具 API 请求/响应模型与参数规格。"""

import re
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.tenant.tools.models import ToolType
from app.tenant.tags.schemas.tag import TagRefOut

SLUG_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


# 单个工具参数的 JSON Schema 风格描述。
class ToolParameterSpec(BaseModel):
    name: str = Field(description="参数名称")
    type: str = Field(default="string", description="参数类型")
    description: str | None = Field(default=None, description="参数说明")
    required: bool = Field(default=False, description="是否必填")
    default: Any = Field(default=None, description="默认值")
    enum: list | None = Field(default=None, description="枚举可选值列表")


# 创建工具请求；slug 与内置工具冲突会被服务层拒绝。
class ToolCreate(BaseModel):
    slug: str = Field(..., min_length=1, max_length=64, description="工具唯一标识（小写字母开头）")
    name: str = Field(..., min_length=1, max_length=128, description="工具名称")
    description: str | None = Field(default=None, description="工具描述")
    tool_type: ToolType = Field(default=ToolType.HTTP, description="工具类型")
    category_id: UUID | None = Field(default=None, description="分类 ID")
    tag_ids: list[UUID] = Field(default_factory=list, description="标签 ID 列表")
    version: str = Field(default="1.0.0", description="版本号")
    require_confirmation: bool = Field(default=False, description="调用前是否需要用户确认")
    parameters: list[ToolParameterSpec] = Field(default_factory=list, description="参数定义列表")
    config: dict = Field(default_factory=dict, description="工具配置 JSON")

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        """校验 slug 命名规则：小写字母开头，仅含小写字母/数字/下划线。"""
        s = v.strip()
        if not SLUG_RE.match(s):
            raise ValueError("slug 须为小写字母开头，仅含小写字母、数字、下划线")
        return s


# 工具局部更新请求。
class ToolUpdate(BaseModel):
    slug: str | None = Field(default=None, description="工具唯一标识")
    name: str | None = Field(default=None, description="工具名称")
    description: str | None = Field(default=None, description="工具描述")
    category_id: UUID | None = Field(default=None, description="分类 ID")
    tag_ids: list[UUID] | None = Field(default=None, description="标签 ID 列表（全量替换）")
    version: str | None = Field(default=None, description="版本号")
    require_confirmation: bool | None = Field(default=None, description="调用前是否需要用户确认")
    parameters: list[ToolParameterSpec] | None = Field(default=None, description="参数定义列表")
    config: dict | None = Field(default=None, description="工具配置 JSON")
    is_active: bool | None = Field(default=None, description="是否启用")

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str | None) -> str | None:
        """同 ``ToolCreate.validate_slug``，但允许 ``None`` 表示不更新。"""
        if v is None:
            return v
        s = v.strip()
        if not SLUG_RE.match(s):
            raise ValueError("slug 须为小写字母开头，仅含小写字母、数字、下划线")
        return s


# 工具详情/列表输出。
class ToolOut(BaseModel):
    id: UUID = Field(description="工具 ID")
    tenant_id: UUID = Field(description="租户 ID")
    slug: str = Field(description="工具唯一标识")
    name: str = Field(description="工具名称")
    description: str | None = Field(default=None, description="工具描述")
    tool_type: ToolType = Field(description="工具类型")
    category_id: UUID | None = Field(default=None, description="分类 ID")
    category_name: str | None = Field(default=None, description="分类名称")
    tags: list[TagRefOut] = Field(default_factory=list, description="标签列表")
    version: str = Field(description="版本号")
    require_confirmation: bool = Field(description="调用前是否需要用户确认")
    parameters: list[dict] = Field(description="参数定义列表")
    config: dict = Field(description="工具配置 JSON")
    is_active: bool = Field(description="是否启用")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")

    model_config = {"from_attributes": True}


# 工具试调用请求。
class ToolInvokeRequest(BaseModel):
    params: dict = Field(default_factory=dict, description="调用参数")
    tool_id: UUID | None = Field(default=None, description="指定工具 ID")
    confirmed: bool = Field(default=False, description="是否已确认执行")


# 等待用户确认的工具调用描述。
class PendingToolCall(BaseModel):
    slug: str = Field(description="工具 slug")
    name: str = Field(description="工具展示名")
    description: str | None = Field(default=None, description="工具说明")
    params: dict = Field(default_factory=dict, description="待执行参数")


# 试调用结果；``pending`` 非空表示需确认后才执行。
class ToolInvokeResult(BaseModel):
    tool: str = Field(description="工具标识")
    source: str = Field(description="工具来源")
    status: str = Field(default="success", description="调用状态")
    output: dict = Field(default_factory=dict, description="调用输出")
    pending: PendingToolCall | None = Field(default=None, description="待确认的工具调用")


# 工具调用审计输出。
class ToolInvocationLogOut(BaseModel):
    id: UUID = Field(description="日志 ID")
    tool_slug: str = Field(description="工具 slug")
    tool_id: UUID | None = Field(default=None, description="工具 ID")
    source: str = Field(description="工具来源")
    status: str = Field(description="调用状态")
    params: dict = Field(description="调用参数")
    output: dict | None = Field(default=None, description="调用输出")
    error_message: str | None = Field(default=None, description="错误信息")
    latency_ms: int = Field(description="调用耗时（毫秒）")
    invoke_source: str = Field(description="调用来源（如 chat、api）")
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}


# 工具目录项：内置与租户工具合并后的统一结构。
class ToolCatalogItem(BaseModel):
    source: str = Field(description="目录来源")
    slug: str = Field(description="工具 slug")
    name: str = Field(description="工具名称")
    description: str | None = Field(default=None, description="工具描述")
    category_id: UUID | None = Field(default=None, description="分类 ID")
    category_name: str | None = Field(default=None, description="分类名称")
    parameters: list[dict] = Field(default_factory=list, description="参数定义列表")
    version: str | None = Field(default=None, description="版本号")
    require_confirmation: bool = Field(default=False, description="调用前是否需要用户确认")
    tool_id: UUID | None = Field(default=None, description="已注册工具 ID")
    tool_type: str | None = Field(default=None, description="工具类型")
    updated_at: datetime | None = Field(default=None, description="更新时间")
