"""租户工作台分类（只读）响应模型。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.category import CategoryDomain


class CategoryOut(BaseModel):
    """全局 sys_categories 行。"""

    id: UUID
    domain: CategoryDomain | str = Field(..., description="agent | prompt | skill | tool")
    parent_id: UUID | None = Field(None, description="预留层级")
    name: str
    slug: str
    sort_order: int
    is_system: bool = True
    created_at: datetime

    model_config = {"from_attributes": True}
