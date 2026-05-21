from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.app_tenant.tools.models import ToolType


class ToolCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    tool_type: ToolType = ToolType.HTTP
    config: dict = Field(default_factory=dict)


class ToolOut(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    tool_type: ToolType
    config: dict
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
