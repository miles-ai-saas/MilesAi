from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.model_catalog import ModelCapabilityType, ModelVendor


class ModelCatalogCreate(BaseModel):
    name: str
    vendor: str = Field(default=ModelVendor.DEEPSEEK.value)
    provider: str | None = None
    model_name: str
    model_code: str
    model_type: str = Field(default=ModelCapabilityType.LLM.value)
    description: str | None = None
    context_window: str | None = None
    api_base: str | None = None
    api_key: str | None = None
    badge: str | None = None
    sort_order: int = 0
    is_featured: bool = False


class ModelCatalogUpdate(BaseModel):
    name: str | None = None
    vendor: str | None = None
    provider: str | None = None
    model_name: str | None = None
    model_code: str | None = None
    model_type: str | None = None
    description: str | None = None
    context_window: str | None = None
    api_base: str | None = None
    api_key: str | None = None
    clear_api_key: bool | None = None
    badge: str | None = None
    sort_order: int | None = None
    is_featured: bool | None = None
    is_active: bool | None = None


class ModelCatalogOut(BaseModel):
    id: UUID
    name: str
    vendor: str
    provider: str
    model_name: str
    model_code: str | None
    model_type: str
    description: str | None
    context_window: str | None
    badge: str | None
    sort_order: int
    is_featured: bool
    publish_status: str
    is_active: bool
    api_base: str | None
    has_api_key: bool
    created_at: datetime

    model_config = {"from_attributes": True}
