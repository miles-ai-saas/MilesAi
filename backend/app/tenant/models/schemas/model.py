from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.model_catalog import ModelCapabilityType, ModelVendor


class ModelConfigCreate(BaseModel):
    name: str = Field(description="配置名称")
    vendor: str = Field(
        default=ModelVendor.OTHER.value,
        description="厂商标识",
    )
    provider: str | None = Field(default=None, description="供应商标识")
    model_name: str = Field(description="模型展示名")
    model_code: str | None = Field(default=None, description="API 调用的模型代码")
    model_type: str = Field(
        default=ModelCapabilityType.LLM.value,
        description="能力类型（如 llm、embedding）",
    )
    description: str | None = Field(default=None, description="描述")
    api_base: str | None = Field(default=None, description="API Base URL")
    api_key: str | None = Field(default=None, description="API Key")
    extra: dict = Field(default={}, description="扩展配置 JSON")


class ModelConfigUpdate(BaseModel):
    name: str | None = Field(default=None, description="配置名称")
    vendor: str | None = Field(default=None, description="厂商标识")
    provider: str | None = Field(default=None, description="供应商标识")
    model_name: str | None = Field(default=None, description="模型展示名")
    model_code: str | None = Field(default=None, description="API 调用的模型代码")
    model_type: str | None = Field(default=None, description="能力类型")
    description: str | None = Field(default=None, description="描述")
    api_base: str | None = Field(default=None, description="API Base URL")
    api_key: str | None = Field(default=None, description="API Key")
    is_active: bool | None = Field(default=None, description="是否启用")
    extra: dict | None = Field(default=None, description="扩展配置 JSON")


class ModelBuiltinCredentialsIn(BaseModel):
    api_base: str | None = Field(default=None, description="API Base URL")
    api_key: str = Field(description="API Key")


class ModelConfigOut(BaseModel):
    id: UUID = Field(description="模型配置 ID")
    source: str = Field(description="来源：builtin | custom")
    name: str = Field(description="配置名称")
    vendor: str = Field(description="厂商标识")
    provider: str = Field(description="供应商标识")
    model_name: str = Field(description="模型展示名")
    model_code: str | None = Field(default=None, description="API 调用的模型代码")
    model_type: str = Field(description="能力类型")
    description: str | None = Field(default=None, description="描述")
    context_window: str | None = Field(default=None, description="上下文窗口说明")
    badge: str | None = Field(default=None, description="展示角标")
    api_base: str | None = Field(default=None, description="API Base URL")
    is_active: bool = Field(description="是否启用")
    publish_status: str | None = Field(default=None, description="发布状态")
    credential_status: str = Field(
        default="missing",
        description="凭证状态",
    )
    has_api_key: bool = Field(default=False, description="是否已配置 API Key")
    extra: dict = Field(default={}, description="扩展配置")
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}


class ModelVendorOption(BaseModel):
    value: str = Field(description="厂商值")
    label: str = Field(description="厂商展示名")


class ModelTypeOption(BaseModel):
    value: str = Field(description="能力类型值")
    label: str = Field(description="能力类型展示名")


class ModelCatalogMetaOut(BaseModel):
    vendors: list[ModelVendorOption] = Field(description="厂商选项列表")
    model_types: list[ModelTypeOption] = Field(description="能力类型选项列表")
