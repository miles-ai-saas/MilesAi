"""标签摘要 DTO（跨域共用的中立模型）。

``TagRefOut`` 嵌在 Agent / Prompt / Skill / Tool / Flow / Marketplace 等资源的 ``tags`` 字段；
为让中立 DTO 模块（如 ``models.marketplace.dto``）也能引用而不反向依赖租户域，
由 ``tenant.tags.schemas.tag`` 下沉至此（该路径转 re-export 保持稳定）。
"""

from uuid import UUID

from pydantic import BaseModel, Field


class TagRefOut(BaseModel):
    """资源上挂载的标签摘要（列表/详情）。"""

    id: UUID = Field(description="标签 ID")
    name: str = Field(description="展示名")
    slug: str = Field(description="租户内唯一标识（slug）")
