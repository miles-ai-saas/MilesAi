"""MCP 枚举展示元数据（GET /mcp/meta）。

- statuses / transport_filters / transport_types / sync_displays
- stdio_templates：预置 STDIO 启动模板（填入 connection_config）
- sync_displays 由 sync_error、tools_cache 推导，与 ORM status 互补
- 前端：lib/mcp-labels.ts、hooks/use-mcp-meta.ts
- 约定：docs/guides/hooks.md §9
"""

from miles_common.schemas.enum_meta import META_SCHEMA_VERSION, enum_options, literal_options
from miles_exec.mcp.constants import McpTransport
from miles_portal.tenant.mcp.models import McpStatus

MCP_STATUS_LABELS: dict[str, tuple[str, str | None]] = {
    McpStatus.ACTIVE.value: ("正常", "最近一次同步成功且有工具列表"),
    McpStatus.INACTIVE.value: ("未激活", "新建或尚未成功同步"),
    McpStatus.ERROR.value: ("异常", "同步失败或协议不可用"),
}

TRANSPORT_OPTIONS: list[tuple[str, str, str | None]] = [
    ("", "全部", "不过滤传输类型"),
    (McpTransport.HTTP.value, "HTTP", "Streamable HTTP JSON-RPC"),
    (McpTransport.SSE.value, "SSE", "Legacy SSE + POST message"),
    (McpTransport.STDIO.value, "STDIO", "沙箱 Runner（需 MCP_RUNNER_ENABLED）"),
]

TRANSPORT_TYPE_OPTIONS: list[tuple[str, str, str | None]] = [
    (McpTransport.HTTP.value, "HTTP", None),
    (McpTransport.SSE.value, "SSE", None),
    (McpTransport.STDIO.value, "STDIO", None),
]

# 卡片展示：由 sync_error / tools_cache 推导，与 ORM status 互补
SYNC_DISPLAY_OPTIONS: list[tuple[str, str, str | None]] = [
    ("synced", "已同步", "有工具缓存且无 sync_error"),
    ("unsynced", "未同步", "尚未拉取 tools/list"),
    ("sync_failed", "同步失败", "sync_error 非空"),
]

#: 预置 STDIO 模板；包名须落在 MCP_RUNNER_NPX_PACKAGE_WHITELIST（默认官方包）
STDIO_TEMPLATES: list[dict] = [
    {
        "id": "mcp-filesystem",
        "label": "官方 Filesystem",
        "hint": "读写指定目录；默认 deny 网络",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp/milesai-mcp-demo"],
        "network_mode": "deny",
    },
    {
        "id": "mcp-memory",
        "label": "官方 Memory",
        "hint": "知识图谱记忆；适合多轮演示",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-memory"],
        "network_mode": "deny",
    },
    {
        "id": "mcp-everything",
        "label": "官方 Everything",
        "hint": "协议全量演示；npx 拉包需 network_mode=allow 或镜像预装",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-everything"],
        "network_mode": "allow",
    },
    {
        "id": "mcp-fetch",
        "label": "官方 Fetch",
        "hint": "HTTP 抓取；需 allow 出站",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-fetch"],
        "network_mode": "allow",
    },
    {
        "id": "mcp-sequential-thinking",
        "label": "官方 Sequential Thinking",
        "hint": "分步推理工具",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
        "network_mode": "deny",
    },
]


def mcp_meta_dict() -> dict:
    """构建 meta 响应 dict，供 *MetaOut.model_validate 与单测使用。"""
    return {
        "statuses": enum_options(McpStatus, MCP_STATUS_LABELS),
        "transport_filters": literal_options(TRANSPORT_OPTIONS),
        "transport_types": literal_options(TRANSPORT_TYPE_OPTIONS),
        "sync_displays": literal_options(SYNC_DISPLAY_OPTIONS),
        "stdio_templates": list(STDIO_TEMPLATES),
        "schema_version": META_SCHEMA_VERSION,
    }
