"""
MCP 服务 API 请求/响应模型（与 ORM ``McpService`` 对应）。

``connection_config`` 常用键：``headers``、``timeout_sec``、``mcp_initialize``、``session_id``（SSE 会话）。
详见 docs/guides/mcp.md。
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.tenant.mcp.models import McpStatus


class McpServiceCreate(BaseModel):
    """注册 MCP；SSE 时 endpoint_url 为 GET 长连接入口（如 /sse）。"""

    name: str = Field(..., min_length=1, max_length=128)
    endpoint_url: str | None = Field(None, max_length=512)
    transport: str = Field("sse", description="http | sse | stdio")
    description: str | None = Field(None, max_length=512)
    connection_config: dict = Field(default_factory=dict)


class McpServiceUpdate(BaseModel):
    """部分更新；传 connection_config 时整对象替换。"""

    name: str | None = Field(None, min_length=1, max_length=128)
    endpoint_url: str | None = Field(None, max_length=512)
    transport: str | None = None
    description: str | None = Field(None, max_length=512)
    connection_config: dict | None = None


class McpServiceOut(BaseModel):
    """列表/详情返回；含 tools_cache 与 sync_error 供前端卡片渲染。"""

    id: UUID
    tenant_id: UUID
    name: str
    endpoint_url: str
    transport: str
    description: str | None
    connection_config: dict
    sync_error: str | None
    tools_cache: list
    last_sync_at: datetime | None
    status: McpStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class McpSyncResult(BaseModel):
    """POST /mcp/{id}/sync 返回的工具快照与时间戳。"""

    tools: list[dict]
    synced_at: datetime


class McpToolInvokeRequest(BaseModel):
    """试调用请求体，对应 MCP tools/call 的 arguments。"""

    params: dict = Field(default_factory=dict)


class McpToolInvokeResult(BaseModel):
    """试调用结果；output 经 rpc.normalize_tool_call_result 规范化。"""

    service_id: UUID
    tool_name: str
    output: dict
