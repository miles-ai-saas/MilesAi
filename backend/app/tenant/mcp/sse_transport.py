"""
MCP 长连接 SSE 传输实现。

支持两种与 MCP 规范相关的模式：

1. Legacy HTTP+SSE（2024-11-05）
   GET 打开 SSE → 首条 event:endpoint 给出 POST URL → POST JSON-RPC → event:message 收响应。

2. Streamable HTTP（2025-03-26+）
   单 URL POST；响应 Content-Type 可为 application/json 或 text/event-stream。

调用方
----
由 ``tenant.mcp.client.mcp_json_rpc`` 按 transport 分支调用；勿在业务层直接 import 本模块。

详见 docs/guides/mcp.md。
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from app.core.logging import get_logger
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from httpx_sse import EventSource, aconnect_sse

from app.common.exceptions import BadRequestError
from app.tenant.mcp.rpc import parse_jsonrpc_result
from app.tenant.mcp.constants import (
    MCP_CLIENT_INFO,
    MCP_PROTOCOL_VERSION,
    MCP_SESSION_HEADER,
)
from app.tenant.mcp.security import validate_mcp_endpoint_url

logger = get_logger(__name__)

CLIENT_INFO = MCP_CLIENT_INFO

# 进程内递增的 JSON-RPC id（每次 RPC 独立会话，无需全局唯一到 UUID）
_rpc_id_counter = 0


def _next_rpc_id() -> int:
    global _rpc_id_counter
    _rpc_id_counter += 1
    return _rpc_id_counter


def _merge_headers(connection_config: dict | None, *, sse_get: bool = False) -> dict[str, str]:
    """合并租户配置的 headers；sse_get 时仅请求事件流。"""
    cfg = connection_config or {}
    if sse_get:
        base = {"Accept": "text/event-stream"}
    else:
        # Streamable HTTP 要求同时接受 JSON 与 SSE 响应
        base = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
    extra = cfg.get("headers")
    if isinstance(extra, dict):
        for k, v in extra.items():
            if k and v is not None:
                base[str(k)] = str(v)
    return base


def _assert_same_origin(base_url: str, target_url: str) -> str:
    """
    校验 endpoint 事件中的 POST URL 与 SSE GET 同源。

    防止恶意 MCP 服务在 endpoint 事件中返回外域 URL（SSRF）。
    """
    base = urlparse(base_url)
    target = urlparse(target_url)
    if base.scheme != target.scheme or base.netloc != target.netloc:
        raise BadRequestError(f"MCP SSE endpoint 与连接不同源: {target_url}")
    return target_url


def _json_from_sse_data(data: str) -> dict:
    """解析 SSE event data 字段为 JSON-RPC 对象。"""
    try:
        parsed = json.loads(data)
    except json.JSONDecodeError as e:
        raise BadRequestError("MCP SSE 消息不是有效 JSON") from e
    if not isinstance(parsed, dict):
        raise BadRequestError("MCP SSE 消息格式无效")
    return parsed


async def _read_sse_until_response(
    response: httpx.Response,
    request_id: int,
    *,
    read_timeout: float,
) -> dict:
    """
    消费 Streamable HTTP POST 返回的 SSE 体，直到出现匹配 request_id 的 JSON-RPC 消息。

    忽略无 data 的 keep-alive 事件；非 message 类型事件跳过。
    """
    event_source = EventSource(response)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + read_timeout
    async for sse in event_source.aiter_sse():
        if loop.time() > deadline:
            raise BadRequestError(f"MCP SSE 响应超时（{read_timeout}s）")
        if sse.event not in (None, "message"):
            continue
        if not sse.data:
            continue
        message = _json_from_sse_data(sse.data)
        if message.get("id") == request_id:
            return message
    raise BadRequestError("MCP SSE 流结束但未收到 JSON-RPC 响应")


async def streamable_http_json_rpc(
    endpoint_url: str,
    method: str,
    params: dict,
    *,
    connection_config: dict | None = None,
    timeout: float = 60.0,
) -> Any:
    """
    Streamable HTTP 单端点 JSON-RPC。

    每次调用独立 POST；若响应带 mcp-session-id 会写回 connection_config 供后续复用（当前上层多为无状态单次调用）。
    """
    url = validate_mcp_endpoint_url(endpoint_url)
    rpc_id = _next_rpc_id()
    body = {"jsonrpc": "2.0", "id": rpc_id, "method": method, "params": params}
    headers = _merge_headers(connection_config)
    session_id = (connection_config or {}).get("session_id")
    if isinstance(session_id, str) and session_id:
        headers[MCP_SESSION_HEADER] = session_id

    connect_timeout = min(timeout, 30.0)
    limits = httpx.Timeout(connect_timeout, read=timeout, write=timeout, pool=connect_timeout)

    try:
        async with httpx.AsyncClient(timeout=limits, follow_redirects=False) as client:
            async with client.stream("POST", url, json=body, headers=headers) as resp:
                if resp.status_code == 202:
                    # 规范允许异步处理；当前实现不轮询，直接报错
                    raise BadRequestError("MCP 已接受请求（202）但未返回可解析结果")
                if resp.status_code >= 400:
                    snippet = (await resp.aread())[:200]
                    raise BadRequestError(f"MCP HTTP {resp.status_code}: {snippet!r}")

                new_session = resp.headers.get(MCP_SESSION_HEADER)
                if new_session and connection_config is not None:
                    connection_config["session_id"] = new_session

                ct = (resp.headers.get("content-type") or "").lower()
                if "application/json" in ct:
                    data = json.loads(await resp.aread())
                    return parse_jsonrpc_result(data)
                if "text/event-stream" in ct:
                    message = await _read_sse_until_response(resp, rpc_id, read_timeout=timeout)
                    return parse_jsonrpc_result(message)
                raise BadRequestError(f"MCP 不支持的 Content-Type: {ct or '(empty)'}")
    except httpx.TimeoutException as e:
        raise BadRequestError(f"MCP 请求超时（{timeout}s）") from e
    except httpx.RequestError as e:
        raise BadRequestError(f"MCP 连接失败: {e}") from e


async def legacy_sse_json_rpc(
    endpoint_url: str,
    method: str,
    params: dict,
    *,
    connection_config: dict | None = None,
    timeout: float = 60.0,
    connect_timeout: float = 15.0,
) -> Any:
    """
    Legacy HTTP+SSE 一次完整 RPC（含可选 initialize 握手）。

    endpoint_url 必须是 SSE GET 入口（如 /sse），不是 /messages POST 地址。
    后台协程 sse_reader 与主流程 rpc_roundtrip 通过 pending[id] Future 配对响应。
    """
    sse_url = validate_mcp_endpoint_url(endpoint_url)
    post_headers = _merge_headers(connection_config)
    get_headers = _merge_headers(connection_config, sse_get=True)

    read_timeout = max(timeout, 30.0)
    limits = httpx.Timeout(connect_timeout, read=read_timeout, write=timeout, pool=connect_timeout)

    endpoint_ready = asyncio.Event()
    post_url_box: dict[str, str | None] = {"url": None}
    # 按 JSON-RPC id 等待 SSE message 事件中的对应响应
    pending: dict[int, asyncio.Future[dict]] = {}

    async def sse_reader(client: httpx.AsyncClient) -> None:
        """长连接读循环：解析 endpoint 与 message 事件。"""
        try:
            async with aconnect_sse(client, "GET", sse_url, headers=get_headers) as event_source:
                event_source.response.raise_for_status()
                async for sse in event_source.aiter_sse():
                    if sse.event == "endpoint":
                        if not sse.data:
                            continue
                        resolved = urljoin(sse_url, sse.data.strip())
                        _assert_same_origin(sse_url, resolved)
                        post_url_box["url"] = resolved
                        endpoint_ready.set()
                    elif sse.event in (None, "message"):
                        if not sse.data:
                            continue
                        message = _json_from_sse_data(sse.data)
                        rid = message.get("id")
                        if isinstance(rid, int) and rid in pending:
                            fut = pending[rid]
                            if not fut.done():
                                fut.set_result(message)
        except Exception as e:
            # 读流失败时唤醒所有等待中的 RPC
            for fut in pending.values():
                if not fut.done():
                    fut.set_exception(e)

    async def rpc_roundtrip(
        client: httpx.AsyncClient,
        post_url: str,
        rpc_method: str,
        rpc_params: dict,
    ) -> dict:
        """向 message URL POST 一条请求，并在 SSE 流上等待同 id 的响应。"""
        rpc_id = _next_rpc_id()
        pending[rpc_id] = asyncio.get_running_loop().create_future()
        payload = {"jsonrpc": "2.0", "id": rpc_id, "method": rpc_method, "params": rpc_params}
        resp = await client.post(post_url, json=payload, headers=post_headers)
        if resp.status_code >= 400:
            snippet = (resp.text or "")[:200]
            raise BadRequestError(f"MCP POST {resp.status_code}: {snippet}")
        try:
            return await asyncio.wait_for(pending[rpc_id], timeout=timeout)
        except asyncio.TimeoutError as e:
            raise BadRequestError(f"MCP SSE 等待「{rpc_method}」响应超时（{timeout}s）") from e
        finally:
            pending.pop(rpc_id, None)

    reader: asyncio.Task[None] | None = None
    try:
        async with httpx.AsyncClient(timeout=limits, follow_redirects=False) as client:
            reader = asyncio.create_task(sse_reader(client))
            try:
                await asyncio.wait_for(endpoint_ready.wait(), timeout=connect_timeout)
            except asyncio.TimeoutError as e:
                raise BadRequestError(
                    f"MCP SSE 未在 {connect_timeout}s 内收到 endpoint 事件；"
                    "请确认 URL 为 SSE GET 入口（例如 /sse）",
                ) from e

            post_url = post_url_box["url"]
            if not post_url:
                raise BadRequestError("MCP SSE endpoint 事件缺少 POST URL")

            # 多数 MCP Server 要求先 initialize；可用 connection_config.mcp_initialize=false 跳过
            do_init = (connection_config or {}).get("mcp_initialize", True)
            if do_init:
                init_msg = await rpc_roundtrip(
                    client,
                    post_url,
                    "initialize",
                    {
                        "protocolVersion": MCP_PROTOCOL_VERSION,
                        "capabilities": {},
                        "clientInfo": CLIENT_INFO,
                    },
                )
                parse_jsonrpc_result(init_msg)
                # 通知无 id，不等待 SSE 响应
                notif = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
                notif_resp = await client.post(post_url, json=notif, headers=post_headers)
                if notif_resp.status_code >= 400:
                    logger.warning("MCP notifications/initialized 返回 %s", notif_resp.status_code)

            message = await rpc_roundtrip(client, post_url, method, params)
            return parse_jsonrpc_result(message)
    except httpx.TimeoutException as e:
        raise BadRequestError("MCP SSE 连接超时") from e
    except httpx.RequestError as e:
        raise BadRequestError(f"MCP SSE 连接失败: {e}") from e
    finally:
        if reader is not None:
            reader.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await reader
