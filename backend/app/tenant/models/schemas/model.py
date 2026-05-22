from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.model_catalog import ModelCapabilityType, ModelVendor


class ModelConfigCreate(BaseModel):
    name: str
    vendor: str = Field(default=ModelVendor.OTHER.value)
    provider: str | None = None
    model_name: str
    model_code: str | None = None
    model_type: str = Field(default=ModelCapabilityType.LLM.value)
    description: str | None = None
    api_base: str | None = None
    api_key: str | None = None
    extra: dict = {}


class ModelConfigUpdate(BaseModel):
    name: str | None = None
    vendor: str | None = None
    provider: str | None = None
    model_name: str | None = None
    model_code: str | None = None
    model_type: str | None = None
    description: str | None = None
    api_base: str | None = None
    api_key: str | None = None
    is_active: bool | None = None
    extra: dict | None = None


class ModelBuiltinCredentialsIn(BaseModel):
    api_base: str | None = None
    api_key: str


class ModelConfigOut(BaseModel):
    id: UUID
    source: str
    name: str
    vendor: str
    provider: str
    model_name: str
    model_code: str | None = None
    model_type: str
    description: str | None = None
    context_window: str | None = None
    badge: str | None = None
    api_base: str | None = None
    is_active: bool
    publish_status: str | None = None
    credential_status: str = "missing"
    has_api_key: bool = False
    extra: dict = {}
    created_at: datetime

    model_config = {"from_attributes": True}


class ModelVendorOption(BaseModel):
    value: str
    label: str


class ModelTypeOption(BaseModel):
    value: str
    label: str


class ModelCatalogMetaOut(BaseModel):
    vendors: list[ModelVendorOption]
    model_types: list[ModelTypeOption]
