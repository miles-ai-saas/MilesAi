from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.app_tenant.tools.models import ToolType


class ToolCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    tool_type: ToolType = ToolType.HTTP
    config: dict = Field(default_factory=dict)


class ToolUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    config: dict | None = None
    is_active: bool | None = None


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


class ToolInvokeRequest(BaseModel):
    params: dict = Field(default_factory=dict)
    tool_id: UUID | None = None


class ToolInvokeResult(BaseModel):
    tool: str
    source: str
    output: dict


class ToolCatalogItem(BaseModel):
    source: str
    name: str
    description: str | None = None
    tool_id: UUID | None = None
    mcp_service_id: UUID | None = None
    mcp_service_name: str | None = None
