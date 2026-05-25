"""运营端应用市场分类（mkt_categories）。"""

from uuid import UUID

from pydantic import BaseModel, Field


class MarketplaceCategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    slug: str | None = Field(None, max_length=64)
    sort_order: int = 0


class MarketplaceCategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=64)
    slug: str | None = Field(None, max_length=64)
    sort_order: int | None = None


class MarketplaceCategoryOut(BaseModel):
    id: UUID
    name: str
    slug: str
    sort_order: int
    app_count: int = 0

    model_config = {"from_attributes": True}
