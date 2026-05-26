"""运营端应用市场分类（mkt_categories）。"""

from uuid import UUID

from pydantic import BaseModel, Field


class MarketplaceCategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, description="分类名称")
    slug: str | None = Field(None, max_length=64, description="URL 标识（slug）")
    sort_order: int = Field(0, description="排序权重")


class MarketplaceCategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=64, description="分类名称")
    slug: str | None = Field(None, max_length=64, description="URL 标识（slug）")
    sort_order: int | None = Field(None, description="排序权重")


class MarketplaceCategoryOut(BaseModel):
    id: UUID = Field(description="分类 ID")
    name: str = Field(description="分类名称")
    slug: str = Field(description="URL 标识（slug）")
    sort_order: int = Field(description="排序权重")
    app_count: int = Field(0, description="关联应用数量")

    model_config = {"from_attributes": True}
