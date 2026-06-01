"""租户工作台分类（只读）响应模型。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.meta.category import CategoryDomain


class CategoryOut(BaseModel):
    """全局 sys_categories 行。"""

    id: UUID = Field(description="分类 ID")
    domain: CategoryDomain | str = Field(..., description="agent | prompt | skill | tool")
    parent_id: UUID | None = Field(default=None, description="预留层级")
    name: str = Field(description="分类名称")
    slug: str = Field(description="分类唯一标识（slug）")
    sort_order: int = Field(description="排序序号")
    is_system: bool = Field(default=True, description="是否为系统内置分类")
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}
