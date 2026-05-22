from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.tenant.mcp.models import McpStatus


class McpServiceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    endpoint_url: str = Field(..., max_length=512)
    transport: str = "sse"


class McpServiceOut(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    endpoint_url: str
    transport: str
    tools_cache: list
    last_sync_at: datetime | None
    status: McpStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class McpSyncResult(BaseModel):
    tools: list[dict]
    synced_at: datetime


class McpToolInvokeRequest(BaseModel):
    params: dict = Field(default_factory=dict)


class McpToolInvokeResult(BaseModel):
    service_id: UUID
    tool_name: str
    output: dict
