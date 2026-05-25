from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.tenant.tags.schemas.tag import TagRefOut


class PromptTemplateCreate(BaseModel):
    category_id: UUID | None = None
    tag_ids: list[UUID] = []
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    content: str = Field(..., min_length=1)


class PromptTemplateUpdate(BaseModel):
    category_id: UUID | None = None
    tag_ids: list[UUID] | None = None
    name: str | None = None
    description: str | None = None
    content: str | None = None
    is_active: bool | None = None


class PromptTemplateOut(BaseModel):
    id: UUID
    tenant_id: UUID
    category_id: UUID | None = None
    category_name: str | None = None
    tags: list[TagRefOut] = []
    name: str
    description: str | None
    content: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
