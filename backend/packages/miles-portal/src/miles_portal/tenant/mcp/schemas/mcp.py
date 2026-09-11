"""
MCP 服务 API 请求/响应模型（与 ORM ``McpService`` 对应）。

``connection_config`` 常用键：``headers``、``timeout_sec``、``mcp_initialize``、``session_id``（SSE 会话）。
详见 docs/guides/mcp.md。
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from miles_portal.tenant.mcp.models import McpStatus


class McpServiceCreate(BaseModel):
    """注册 MCP；SSE 时 endpoint_url 为 GET 长连接入口（如 /sse）。"""

    name: str = Field(..., min_length=1, max_length=128, description="服务名称")
    endpoint_url: str | None = Field(
        default=None,
        max_length=512,
        description="MCP 端点 URL",
    )
    transport: str = Field(default="sse", description="传输类型：http | sse | stdio")
    description: str | None = Field(
        default=None,
        max_length=512,
        description="服务描述",
    )
    connection_config: dict = Field(default_factory=dict, description="连接配置 JSON")


class McpServiceUpdate(BaseModel):
    """部分更新；传 connection_config 时整对象替换。"""

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="服务名称",
    )
    endpoint_url: str | None = Field(
        default=None,
        max_length=512,
        description="MCP 端点 URL",
    )
    transport: str | None = Field(default=None, description="传输类型")
    description: str | None = Field(
        default=None,
        max_length=512,
        description="服务描述",
    )
    connection_config: dict | None = Field(default=None, description="连接配置 JSON")


class McpServiceOut(BaseModel):
    """列表/详情返回；含 tools_cache 与 sync_error 供前端卡片渲染。"""

    id: UUID = Field(description="MCP 服务 ID")
    tenant_id: UUID = Field(description="租户 ID")
    name: str = Field(description="服务名称")
    endpoint_url: str = Field(description="MCP 端点 URL")
    transport: str = Field(description="传输类型")
    description: str | None = Field(default=None, description="服务描述")
    connection_config: dict = Field(description="连接配置")
    sync_error: str | None = Field(default=None, description="上次同步错误信息")
    tools_cache: list = Field(description="缓存的工具列表")
    last_sync_at: datetime | None = Field(default=None, description="上次同步时间")
    status: McpStatus = Field(description="服务状态")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")

    model_config = {"from_attributes": True}


class McpSyncResult(BaseModel):
    """POST /mcp/{id}/sync 返回的工具快照与时间戳。"""

    tools: list[dict] = Field(description="同步得到的工具列表")
    synced_at: datetime = Field(description="同步完成时间")


class McpToolInvokeRequest(BaseModel):
    """试调用请求体，对应 MCP tools/call 的 arguments。"""

    params: dict = Field(default_factory=dict, description="工具调用参数")


class McpToolInvokeResult(BaseModel):
    """试调用结果；output 经 rpc.normalize_tool_call_result 规范化。"""

    service_id: UUID = Field(description="MCP 服务 ID")
    tool_name: str = Field(description="工具名称")
    output: dict = Field(description="规范化后的调用结果")
