from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SkillPackageCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    tool_names: list[str] = []
    prompt_snippet: str | None = None
    config: dict = {}


class SkillPackageUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    tool_names: list[str] | None = None
    prompt_snippet: str | None = None
    config: dict | None = None
    is_active: bool | None = None


class SkillPackageOut(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    tool_names: list[str]
    prompt_snippet: str | None
    config: dict
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
