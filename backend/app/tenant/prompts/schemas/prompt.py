from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.tenant.tags.schemas.tag import TagRefOut


class PromptTemplateCreate(BaseModel):
    category_id: UUID | None = Field(default=None, description="分类 ID")
    tag_ids: list[UUID] = Field(default_factory=list, description="标签 ID 列表")
    name: str = Field(..., min_length=1, max_length=128, description="模板名称")
    description: str | None = Field(default=None, description="描述")
    content: str = Field(..., min_length=1, description="提示词正文")


class PromptTemplateUpdate(BaseModel):
    category_id: UUID | None = Field(default=None, description="分类 ID")
    tag_ids: list[UUID] | None = Field(default=None, description="标签 ID 列表")
    name: str | None = Field(default=None, description="模板名称")
    description: str | None = Field(default=None, description="描述")
    content: str | None = Field(default=None, description="提示词正文")
    is_active: bool | None = Field(default=None, description="是否启用")


class PromptTemplateOut(BaseModel):
    id: UUID = Field(description="模板 ID")
    tenant_id: UUID = Field(description="租户 ID")
    category_id: UUID | None = Field(default=None, description="分类 ID")
    category_name: str | None = Field(default=None, description="分类名称")
    tags: list[TagRefOut] = Field(default_factory=list, description="关联标签列表")
    name: str = Field(description="模板名称")
    description: str | None = Field(default=None, description="描述")
    content: str = Field(description="提示词正文")
    is_active: bool = Field(description="是否启用")
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}
