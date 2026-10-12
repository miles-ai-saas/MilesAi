"""运营端内置模型目录 DTO。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from miles_common.schemas.api_enums import ModelCapabilityType, ModelVendor


# 创建内置模型入参。
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
    icon: str | None = Field(None, description="图标键或 URL（写入 extra.icon）")
    sort_order: int = Field(0, description="排序权重")
    is_featured: bool = Field(False, description="是否推荐")


# 更新内置模型入参（含显式清除 API Key 开关）。
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
    icon: str | None = Field(None, description="图标键或 URL（写入 extra.icon；空串清除）")
    sort_order: int | None = Field(None, description="排序权重")
    is_featured: bool | None = Field(None, description="是否推荐")
    is_active: bool | None = Field(None, description="是否启用")


# 内置模型目录输出（不返回明文 API Key）。
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
    icon: str | None = Field(default=None, description="图标键或 URL")
    sort_order: int = Field(description="排序权重")
    is_featured: bool = Field(description="是否推荐")
    publish_status: str = Field(description="发布状态")
    is_active: bool = Field(description="是否启用")
    api_base: str | None = Field(description="API 基础地址")
    has_api_key: bool = Field(description="是否已配置 API 密钥")
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}


class ModelCatalogRefsOut(BaseModel):
    """下架前引用统计。"""

    agents: int = Field(description="引用该模型的智能体数")
    knowledge_bases: int = Field(description="引用该模型的知识库数（embedding/visual/rerank）")
    total: int = Field(description="引用合计")


class ModelCatalogImportItem(BaseModel):
    """批量导入单条；与创建字段对齐，可选发布状态。"""

    name: str = Field(description="模型展示名称")
    vendor: str = Field(default=ModelVendor.DEEPSEEK.value, description="模型厂商")
    provider: str | None = Field(None, description="推理服务提供方")
    model_name: str = Field(description="模型名称（调用标识）")
    model_code: str = Field(description="模型编码（upsert 键）")
    model_type: str = Field(default=ModelCapabilityType.LLM.value, description="模型能力类型")
    description: str | None = Field(None, description="模型描述")
    context_window: str | None = Field(None, description="上下文窗口说明")
    api_base: str | None = Field(None, description="API 基础地址")
    badge: str | None = Field(None, description="展示角标")
    icon: str | None = Field(None, description="图标键或 URL")
    sort_order: int = Field(0, description="排序权重")
    is_featured: bool = Field(False, description="是否推荐")
    publish_status: str | None = Field(
        None,
        description="draft | published | deprecated；默认 draft",
    )


class ModelCatalogImportBody(BaseModel):
    """运营批量导入内置模型。"""

    items: list[ModelCatalogImportItem] = Field(description="导入条目", min_length=1, max_length=200)
    upsert: bool = Field(True, description="同 model_code 已存在时更新元数据（不改 Key）")


class ModelCatalogImportResult(BaseModel):
    """批量导入结果摘要。"""

    created: int = Field(description="新建条数")
    updated: int = Field(description="更新条数")
    skipped: int = Field(description="跳过条数")
    errors: list[str] = Field(default_factory=list, description="逐条错误（含 model_code）")
