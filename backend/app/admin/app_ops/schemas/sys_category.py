"""运营端 sys_categories（全平台全局字典）。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SysCategoryAdminCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, description="分类名称")
    slug: str | None = Field(None, max_length=64, description="URL 标识（slug）")
    sort_order: int = Field(0, description="排序权重")


class SysCategoryAdminUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=64, description="分类名称")
    slug: str | None = Field(None, max_length=64, description="URL 标识（slug）")
    sort_order: int | None = Field(None, description="排序权重")


class SysCategoryAdminOut(BaseModel):
    id: UUID = Field(description="分类 ID")
    domain: str = Field(description="所属业务域")
    name: str = Field(description="分类名称")
    slug: str = Field(description="URL 标识（slug）")
    sort_order: int = Field(description="排序权重")
    is_system: bool = Field(description="是否为系统内置")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime | None = Field(None, description="更新时间")

    model_config = {"from_attributes": True}
