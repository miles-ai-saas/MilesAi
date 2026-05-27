"""
MCP 对外客户端入口：``tools/list`` 同步与 ``tools/call`` 调用（L3 协议层）。

降级链（``mcp_json_rpc``）
-----------------------
::

  transport=sse:
    legacy_sse_json_rpc          # GET /sse → event:endpoint → POST messages
      ↓ 仅当错误含「endpoint 事件」「SSE GET」
    streamable_http_json_rpc     # 单 URL POST，JSON 或 SSE 响应体
      ↓ 非 BadRequestError 的其它异常
    _simple_post_json_rpc        # 最简单 POST application/json

  transport=http:
    streamable_http_json_rpc → _simple_post_json_rpc

``fetch_mcp_tools`` 在 JSON-RPC 失败后另试 GET 同 URL（部分自建服务非标准 MCP）。

上层入口：``McpServiceManager.sync_service`` / ``invoke_tool`` → 本模块。
"""

from __future__ import annotations

from app.core.logging import get_logger
from typing import Any

import httpx

from app.common.exceptions import BadRequestError
from app.tenant.mcp.rpc import normalize_tool_call_result, parse_jsonrpc_result
from app.tenant.mcp.security import validate_mcp_endpoint_url
from app.tenant.mcp.sse_transport import legacy_sse_json_rpc, streamable_http_json_rpc
from app.tenant.mcp.transport import normalize_transport

logger = get_logger(__name__)

DEFAULT_LIST_TIMEOUT = 10.0
DEFAULT_INVOKE_TIMEOUT = 60.0


def _client_timeout(connection_config: dict | None, default: float) -> float:
    """读取 connection_config.timeout_sec，上限 120s。"""
    cfg = connection_config or {}
    raw = cfg.get("timeout_sec")
    if isinstance(raw, (int, float)) and raw > 0:
        return min(float(raw), 120.0)
    return default


def _request_headers(connection_config: dict | None) -> dict[str, str]:
    """简单 POST 降级路径使用的请求头（仅 Accept JSON）。"""
    base = {"Content-Type": "application/json", "Accept": "application/json"}
    cfg = connection_config or {}
    extra = cfg.get("headers")
    if isinstance(extra, dict):
        for k, v in extra.items():
            if k and v is not None:
                base[str(k)] = str(v)
    return base


def _normalize_tools(raw: list | dict) -> list[dict]:
    """将 tools/list 的多种返回形状统一为 [{name, description}, ...] 写入 tools_cache。"""
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict) and "tools" in raw:
        items = raw["tools"]
    else:
        return []
    out: list[dict] = []
    for item in items:
        if isinstance(item, dict):
            name = item.get("name") or item.get("id") or "tool"
            desc = item.get("description") or item.get("summary") or ""
            out.append({"name": str(name), "description": str(desc)})
        elif isinstance(item, str):
            out.append({"name": item, "description": ""})
    return out


async def _simple_post_json_rpc(
    endpoint_url: str,
    method: str,
    params: dict,
    *,
    connection_config: dict | None = None,
    timeout: float | None = None,
) -> Any:
    """最后一级降级：对 endpoint_url 单次 POST，响应体为 application/json。"""
    url = validate_mcp_endpoint_url(endpoint_url)
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    req_timeout = timeout if timeout is not None else _client_timeout(connection_config, DEFAULT_INVOKE_TIMEOUT)
    headers = _request_headers(connection_config)

    try:
        async with httpx.AsyncClient(timeout=req_timeout, follow_redirects=False) as client:
            resp = await client.post(url, json=body, headers=headers)
    except httpx.TimeoutException as e:
        raise BadRequestError(f"MCP 请求超时（{req_timeout}s）") from e
    except httpx.RequestError as e:
        raise BadRequestError(f"MCP 连接失败: {e}") from e

    if not resp.is_success:
        snippet = (resp.text or "")[:200]
        raise BadRequestError(f"MCP HTTP {resp.status_code}: {snippet}")

    try:
        data = resp.json()
    except ValueError as e:
        raise BadRequestError("MCP 响应不是有效 JSON") from e

    return parse_jsonrpc_result(data)


async def mcp_json_rpc(
    endpoint_url: str,
    method: str,
    params: dict,
    *,
    transport: str = "sse",
    connection_config: dict | None = None,
    timeout: float | None = None,
) -> Any:
    """
    统一 JSON-RPC 入口；返回已解析的 **result**（``rpc.parse_jsonrpc_result`` 之后）。

    ``method`` 常用：``tools/list``、``tools/call``、``initialize``（Legacy SSE 内部）。
    """
    t = normalize_transport(transport)
    if t == "stdio":
        raise BadRequestError("STDIO 传输不支持远程 JSON-RPC invoke")

    req_timeout = timeout if timeout is not None else _client_timeout(connection_config, DEFAULT_INVOKE_TIMEOUT)
    cfg = dict(connection_config or {})

    if t == "custom":
        adapter_url = cfg.get("adapter_url") or endpoint_url
        return await _simple_post_json_rpc(
            adapter_url,
            method,
            params,
            connection_config=cfg,
            timeout=req_timeout,
        )

    if t == "sse":
        try:
            return await legacy_sse_json_rpc(
                endpoint_url,
                method,
                params,
                connection_config=cfg,
                timeout=req_timeout,
            )
        except BadRequestError as e:
            msg = e.message or ""
            # 仅「等不到 endpoint」类错误才降级，避免掩盖鉴权/协议错误
            if "endpoint 事件" not in msg and "SSE GET" not in msg:
                raise
            logger.info("MCP legacy SSE 不可用，回退 Streamable HTTP/POST: %s", msg)

    try:
        return await streamable_http_json_rpc(
            endpoint_url,
            method,
            params,
            connection_config=cfg,
            timeout=req_timeout,
        )
    except BadRequestError:
        raise
    except Exception:
        logger.debug("Streamable HTTP 失败，回退简单 POST", exc_info=True)

    return await _simple_post_json_rpc(
        endpoint_url,
        method,
        params,
        connection_config=cfg,
        timeout=req_timeout,
    )


async def fetch_mcp_tools(
    endpoint_url: str,
    transport: str = "sse",
    connection_config: dict | None = None,
) -> list[dict]:
    """
    拉取 ``tools/list`` 并规范化为 ``[{name, description}, ...]`` 写入 ``tools_cache``。

    空列表时 ``McpServiceManager`` 会标 ERROR 并写占位工具行，便于 UI 展示原因。
    最后一级：GET + ``Accept: application/json``（非标准 MCP 兼容）。
    """
    if endpoint_url.startswith("stdio://"):
        return []

    url = validate_mcp_endpoint_url(endpoint_url)
    timeout = _client_timeout(connection_config, DEFAULT_LIST_TIMEOUT)
    t = normalize_transport(transport)

    try:
        result = await mcp_json_rpc(
            url,
            "tools/list",
            {},
            transport=t,
            connection_config=connection_config,
            timeout=timeout,
        )
        if isinstance(result, dict) and "tools" in result:
            tools = _normalize_tools(result["tools"])
            if tools:
                return tools
        if isinstance(result, list):
            tools = _normalize_tools(result)
            if tools:
                return tools
    except BadRequestError:
        raise
    except Exception:
        logger.debug("MCP tools/list 失败，尝试 GET 降级", exc_info=True)

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            resp = await client.get(url, headers={"Accept": "application/json"})
            if resp.is_success and "json" in resp.headers.get("content-type", ""):
                tools = _normalize_tools(resp.json())
                if tools:
                    return tools
    except Exception:
        logger.debug("MCP tools/list GET 降级失败", exc_info=True)

    return []


async def invoke_mcp_tool(
    endpoint_url: str,
    tool_name: str,
    arguments: dict,
    *,
    transport: str = "sse",
    connection_config: dict | None = None,
) -> dict:
    """
    ``tools/call``；``normalize_tool_call_result`` 后若 ``isError`` 抛 ``BadRequestError``。

    工作台试调用入口；与 KB/RAG 无直接关系。
    """
    t = normalize_transport(transport)
    result = await mcp_json_rpc(
        endpoint_url,
        "tools/call",
        {"name": tool_name, "arguments": arguments or {}},
        transport=t,
        connection_config=connection_config,
        timeout=_client_timeout(connection_config, DEFAULT_INVOKE_TIMEOUT),
    )
    output = normalize_tool_call_result(result)
    if output.get("isError"):
        text = output.get("text") or "工具执行返回错误"
        raise BadRequestError(f"MCP 工具执行失败: {text}")
    return output
