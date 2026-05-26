"""categories 模块 GET /categories/meta 响应体。"""

from pydantic import BaseModel, Field

from app.common.schemas.enum_meta import EnumOption


class CategoryMetaOut(BaseModel):
    """资源域枚举（Tab/筛选）；具体分类名仍走 GET /categories?domain=。"""

    domains: list[EnumOption] = Field(description="agent | prompt | skill | tool")
    schema_version: str = "1"
