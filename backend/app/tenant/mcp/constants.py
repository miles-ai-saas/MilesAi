"""MCP 协议与客户端常量（SSE / STDIO / runner 共用）。"""

import enum

MCP_PROTOCOL_VERSION = "2024-11-05"
MCP_SESSION_HEADER = "mcp-session-id"
MCP_CLIENT_INFO = {"name": "milesai", "version": "0.1.0"}


class McpTransport(str, enum.Enum):
    """MCP 连接传输类型（与 ``agt_mcp_services.transport`` 存库值一致）。"""

    HTTP = "http"
    SSE = "sse"
    STDIO = "stdio"
    CUSTOM = "custom"
