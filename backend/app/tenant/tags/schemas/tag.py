"""租户标签 API 模型。

- ``TenantTagOut`` / ``TenantTagCreate``：标签管理接口
- ``TagRefOut``：嵌入 Agent、Prompt、Skill、Tool、Flow 的 ``tags`` 字段
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TagRefOut(BaseModel):
    """资源上挂载的标签摘要（列表/详情）。"""

    id: UUID = Field(description="标签 ID")
    name: str = Field(description="展示名")
    slug: str = Field(description="租户内唯一标识（slug）")


class TenantTagOut(BaseModel):
    """租户标签库中的一条记录。"""

    id: UUID = Field(description="标签 ID")
    tenant_id: UUID = Field(description="租户 ID")
    name: str = Field(..., description="展示名")
    slug: str = Field(..., description="租户内唯一，由 name 自动 slugify")
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}


class TenantTagCreate(BaseModel):
    """创建标签；同名（同 slug）冲突时返回 409。"""

    name: str = Field(..., min_length=1, max_length=64, description="展示名")
