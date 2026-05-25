"""运营端 sys_categories（全平台全局字典）。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SysCategoryAdminCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    slug: str | None = Field(None, max_length=64)
    sort_order: int = 0


class SysCategoryAdminUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=64)
    slug: str | None = Field(None, max_length=64)
    sort_order: int | None = None


class SysCategoryAdminOut(BaseModel):
    id: UUID
    domain: str
    name: str
    slug: str
    sort_order: int
    is_system: bool
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
