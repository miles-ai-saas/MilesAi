from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.model_catalog import ModelCapabilityType, ModelVendor


class ModelCatalogCreate(BaseModel):
    name: str = Field(description="模型展示名称")
    vendor: str = Field(default=ModelVendor.DEEPSEEK.value, description="模型厂商")
    provider: str | None = Field(None, description="推理服务提供方")
    model_name: str = Field(description="模型名称（调用标识）")
    model_code: str = Field(description="模型编码")
    model_type: str = Field(default=ModelCapabilityType.LLM.value, description="模型能力类型")
    description: str | None = Field(None, description="模型描述")
    context_window: str | None = Field(None, description="上下文窗口说明")
    api_base: str | None = Field(None, description="API 基础地址")
    api_key: str | None = Field(None, description="API 密钥")
    badge: str | None = Field(None, description="展示角标")
    sort_order: int = Field(0, description="排序权重")
    is_featured: bool = Field(False, description="是否推荐")


class ModelCatalogUpdate(BaseModel):
    name: str | None = Field(None, description="模型展示名称")
    vendor: str | None = Field(None, description="模型厂商")
    provider: str | None = Field(None, description="推理服务提供方")
    model_name: str | None = Field(None, description="模型名称（调用标识）")
    model_code: str | None = Field(None, description="模型编码")
    model_type: str | None = Field(None, description="模型能力类型")
    description: str | None = Field(None, description="模型描述")
    context_window: str | None = Field(None, description="上下文窗口说明")
    api_base: str | None = Field(None, description="API 基础地址")
    api_key: str | None = Field(None, description="API 密钥")
    clear_api_key: bool | None = Field(None, description="是否清除已保存的 API 密钥")
    badge: str | None = Field(None, description="展示角标")
    sort_order: int | None = Field(None, description="排序权重")
    is_featured: bool | None = Field(None, description="是否推荐")
    is_active: bool | None = Field(None, description="是否启用")


class ModelCatalogOut(BaseModel):
    id: UUID = Field(description="模型目录项 ID")
    name: str = Field(description="模型展示名称")
    vendor: str = Field(description="模型厂商")
    provider: str = Field(description="推理服务提供方")
    model_name: str = Field(description="模型名称（调用标识）")
    model_code: str | None = Field(description="模型编码")
    model_type: str = Field(description="模型能力类型")
    description: str | None = Field(description="模型描述")
    context_window: str | None = Field(description="上下文窗口说明")
    badge: str | None = Field(description="展示角标")
    sort_order: int = Field(description="排序权重")
    is_featured: bool = Field(description="是否推荐")
    publish_status: str = Field(description="发布状态")
    is_active: bool = Field(description="是否启用")
    api_base: str | None = Field(description="API 基础地址")
    has_api_key: bool = Field(description="是否已配置 API 密钥")
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}
