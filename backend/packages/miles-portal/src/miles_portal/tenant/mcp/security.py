"""
MCP 出站连接安全（HTTP/SSE：连接层校验，非 STDIO 执行沙箱）。

生产环境建议 OUTBOUND_ALLOW_PRIVATE_HOSTS=false，避免租户配置的内网 URL 被用作 SSRF。
该开关为**所有出站路径**共用（MCP 端点、HTTP 工具、技能包 Git 导入），
判据集中在 miles_core/url_security.py。详见 docs/architecture/mcp-sandbox.md。
"""

from miles_common.exceptions import BadRequestError
from miles_core.url_security import validate_outbound_url


def validate_mcp_endpoint_url(url: str) -> str:
    """
    校验即将发起 HTTP 请求的 MCP 端点。

    - 仅允许 http/https
    - stdio:// 占位 URL 禁止走远程客户端
    - 可选：拒绝本机/内网（由 outbound_allow_private_hosts 控制，默认放行）
    """
    raw = (url or "").strip()
    if raw.startswith("stdio://"):
        raise BadRequestError("STDIO 端点不支持远程 invoke")
    return validate_outbound_url(raw)
