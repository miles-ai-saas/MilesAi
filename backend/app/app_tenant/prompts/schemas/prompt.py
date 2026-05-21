from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PromptTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    content: str = Field(..., min_length=1)


class PromptTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    content: str | None = None
    is_active: bool | None = None


class PromptTemplateOut(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    content: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
