"""租户标签 API 模型。

- ``TenantTagOut`` / ``TenantTagCreate``：标签管理接口
- ``TagRefOut``：嵌入 Agent、Prompt、Skill、Tool 的 ``tags`` 字段
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TagRefOut(BaseModel):
    """资源上挂载的标签摘要（列表/详情）。"""

    id: UUID
    name: str
    slug: str


class TenantTagOut(BaseModel):
    """租户标签库中的一条记录。"""

    id: UUID
    tenant_id: UUID
    name: str = Field(..., description="展示名")
    slug: str = Field(..., description="租户内唯一，由 name 自动 slugify")
    created_at: datetime

    model_config = {"from_attributes": True}


class TenantTagCreate(BaseModel):
    """创建标签；同名（同 slug）冲突时返回 409。"""

    name: str = Field(..., min_length=1, max_length=64)
