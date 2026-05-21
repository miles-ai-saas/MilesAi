from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ModelConfigCreate(BaseModel):
    name: str
    provider: str = Field(..., description="openai / ollama / dashscope 等")
    model_name: str
    api_base: str | None = None
    api_key: str | None = None
    extra: dict = {}


class ModelConfigUpdate(BaseModel):
    name: str | None = None
    provider: str | None = None
    model_name: str | None = None
    api_base: str | None = None
    api_key: str | None = None
    is_active: bool | None = None
    extra: dict | None = None


class ModelConfigOut(BaseModel):
    id: UUID
    name: str
    provider: str
    model_name: str
    api_base: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
