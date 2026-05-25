import re
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.tenant.tools.models import ToolType
from app.tenant.tags.schemas.tag import TagRefOut

SLUG_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


class ToolParameterSpec(BaseModel):
    name: str
    type: str = "string"
    description: str | None = None
    required: bool = False
    default: Any = None
    enum: list | None = None


class ToolCreate(BaseModel):
    slug: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    tool_type: ToolType = ToolType.HTTP
    category_id: UUID | None = None
    tag_ids: list[UUID] = []
    version: str = "1.0.0"
    require_confirmation: bool = False
    parameters: list[ToolParameterSpec] = Field(default_factory=list)
    config: dict = Field(default_factory=dict)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        s = v.strip()
        if not SLUG_RE.match(s):
            raise ValueError("slug 须为小写字母开头，仅含小写字母、数字、下划线")
        return s


class ToolUpdate(BaseModel):
    slug: str | None = None
    name: str | None = None
    description: str | None = None
    category_id: UUID | None = None
    tag_ids: list[UUID] | None = None
    version: str | None = None
    require_confirmation: bool | None = None
    parameters: list[ToolParameterSpec] | None = None
    config: dict | None = None
    is_active: bool | None = None

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str | None) -> str | None:
        if v is None:
            return v
        s = v.strip()
        if not SLUG_RE.match(s):
            raise ValueError("slug 须为小写字母开头，仅含小写字母、数字、下划线")
        return s


class ToolOut(BaseModel):
    id: UUID
    tenant_id: UUID
    slug: str
    name: str
    description: str | None
    tool_type: ToolType
    category_id: UUID | None
    category_name: str | None = None
    tags: list[TagRefOut] = []
    version: str
    require_confirmation: bool
    parameters: list[dict]
    config: dict
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ToolInvokeRequest(BaseModel):
    params: dict = Field(default_factory=dict)
    tool_id: UUID | None = None
    confirmed: bool = False


class PendingToolCall(BaseModel):
    slug: str
    name: str
    description: str | None = None
    params: dict = Field(default_factory=dict)


class ToolInvokeResult(BaseModel):
    tool: str
    source: str
    status: str = "success"
    output: dict = Field(default_factory=dict)
    pending: PendingToolCall | None = None


class ToolInvocationLogOut(BaseModel):
    id: UUID
    tool_slug: str
    tool_id: UUID | None
    source: str
    status: str
    params: dict
    output: dict | None
    error_message: str | None
    latency_ms: int
    invoke_source: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ToolCatalogItem(BaseModel):
    source: str
    slug: str
    name: str
    description: str | None = None
    category_id: UUID | None = None
    category_name: str | None = None
    parameters: list[dict] = Field(default_factory=list)
    version: str | None = None
    require_confirmation: bool = False
    tool_id: UUID | None = None
    mcp_service_id: UUID | None = None
    mcp_service_name: str | None = None
    updated_at: datetime | None = None
