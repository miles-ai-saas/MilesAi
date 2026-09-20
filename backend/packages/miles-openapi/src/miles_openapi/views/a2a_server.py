"""A2A 对外暴露：Agent Card 发现端点与 JSON-RPC ``message/send`` 调用端点。

多租户寻址见 ``tenant.a2a.server`` 模块 docstring。鉴权：Card GET 公开（A2A 发现
约定，且平台自身的 ``fetch_agent_card`` 不带凭证），调用 POST 须带该智能体的
``X-API-Key``。协议级错误回 JSON-RPC 错误信封（HTTP 200），不套平台
``{code,message,data}`` 信封 —— 外部 A2A 客户端按 JSON-RPC 解析。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.exceptions import NotFoundError
from miles_common.trace import get_trace_id
from miles_core.infra.db import get_db
from miles_core.tenant import TenantContext
from miles_core.web.middlewares.platform_risk import RATE_LIMIT_MESSAGE, client_ip
from miles_portal.tenant.a2a.server import (
    PARSE_ERROR,
    RATE_LIMITED,
    agent_card_well_known_path,
    jsonrpc_error,
)
from miles_portal.tenant.a2a.services.limits import check_a2a_rate_limit
from miles_portal.tenant.a2a.services.server import (
    build_agent_card_by_id,
    handle_a2a_rpc,
    open_a2a_stream,
    read_task_artifact,
    resolve_default_published_agent_id,
)
from miles_portal.tenant.a2a.services.subscription import open_task_subscription
from miles_portal.tenant.agents.deps_api_auth import require_agent_api_key

#: SSE 响应头。``X-Accel-Buffering: no`` 关掉 Nginx 侧缓冲，否则帧会被攒到最后一起发。
_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

router = APIRouter()
well_known_router = APIRouter()


@router.get("/a2a/agents/{agent_id}/.well-known/agent-card.json")
async def get_published_agent_card(
    agent_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """公开 Agent Card；未发布的智能体与不存在的智能体同样返回 404。"""
    card = await build_agent_card_by_id(db, agent_id, base_url=str(request.base_url))
    return JSONResponse(card)


def _stream_or_json(opened: dict | AsyncIterator[str]) -> Response:
    """流式入口的两种返回：前置失败回普通 JSON，通过则回 SSE。

    前置失败不能进 SSE —— 响应头一旦写成 ``text/event-stream``，HTTP 状态码与
    ``Retry-After`` 就没处放了，对端只能从半条流里猜。
    """
    if isinstance(opened, dict):
        return JSONResponse(opened)
    return StreamingResponse(opened, media_type="text/event-stream", headers=_SSE_HEADERS)


@router.post("/a2a/agents/{agent_id}")
async def a2a_jsonrpc(
    agent_id: UUID,
    request: Request,
    ctx: TenantContext = Depends(require_agent_api_key),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """A2A JSON-RPC 端点（``message/send`` / ``message/stream`` / ``tasks/*``）。

    ``message/stream`` 与 ``tasks/resubscribe`` 按 A2A 约定走 SSE，与其它方法共用同一 URL；
    请求体非 JSON 时回 -32700 信封。前置校验失败的流式请求回普通 JSON，不进入 SSE。

    限流在鉴权之后、分发之前：维度取 API Key 行 id（见 ``services.limits``）。超限回
    HTTP 429 + ``Retry-After``，正文仍是 JSON-RPC 错误信封（``-32000``）—— 外部客户端
    按 JSON-RPC 解析，且只有它能把错误对回自己的 ``id``。流式请求也在这里被拦下，
    避免响应头已写成 ``text/event-stream`` 后无处安放状态码。
    """
    try:
        payload = await request.json()
    except ValueError:
        return JSONResponse(jsonrpc_error(None, PARSE_ERROR, "请求体不是合法 JSON"))
    req_id: object = payload.get("id") if isinstance(payload, dict) else None
    hit = await check_a2a_rate_limit(ctx, agent_id, path=request.url.path, ip=client_ip(request))
    if hit is not None:
        return JSONResponse(
            jsonrpc_error(
                req_id,
                RATE_LIMITED,
                RATE_LIMIT_MESSAGE,
                data={"kind": "rate_limit", "retryAfterSeconds": hit.retry_after_seconds},
            ),
            status_code=429,
            headers={"Retry-After": str(hit.retry_after_seconds)},
        )
    base_url = str(request.base_url)
    method = payload.get("method") if isinstance(payload, dict) else None
    if method == "message/stream":
        return _stream_or_json(await open_a2a_stream(db, ctx, agent_id, payload))
    if method == "tasks/resubscribe":
        return _stream_or_json(await open_task_subscription(db, ctx, agent_id, payload, base_url=base_url))
    return JSONResponse(await handle_a2a_rpc(db, ctx, agent_id, payload, base_url=base_url))


@router.get("/a2a/agents/{agent_id}/tasks/{task_id}/artifacts/{attachment_id}")
async def a2a_task_artifact(
    agent_id: UUID,
    task_id: UUID,
    attachment_id: UUID,
    request: Request,
    ctx: TenantContext = Depends(require_agent_api_key),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """任务产物下载（``Task.artifacts[].parts[].file.uri`` 指向此处，须带 ``X-API-Key``）。

    平台不暴露对象存储签名 URL；产物只能经由该鉴权端点取回，且限「该智能体该任务」。
    超限走平台信封 429（本路由是普通 HTTP 下载、不是 JSON-RPC，形状与中间件一致）。
    """
    hit = await check_a2a_rate_limit(ctx, agent_id, path=request.url.path, ip=client_ip(request))
    if hit is not None:
        return JSONResponse(
            status_code=429,
            content={"code": 429, "message": RATE_LIMIT_MESSAGE, "data": None, "trace_id": get_trace_id()},
            headers={"Retry-After": str(hit.retry_after_seconds)},
        )
    data, mime, filename = await read_task_artifact(db, ctx, agent_id, task_id, attachment_id)
    disposition = f"attachment; filename*=UTF-8''{quote(filename)}"
    return Response(content=data, media_type=mime, headers={"Content-Disposition": disposition})


@well_known_router.get("/.well-known/agent-card.json")
async def well_known_agent_card(
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """平台根路径别名：仅在全平台唯一发布时 307 到该智能体的 Card 路径。

    多租户下根路径无法区分租户，命中不唯一时返回 404 而非随意挑一个 —— 否则会把 A
    租户的 Card 发给 B 的对端。
    """
    agent_id = await resolve_default_published_agent_id(db)
    if not agent_id:
        raise NotFoundError("本平台未发布唯一的 A2A Server，请使用按智能体的 Agent Card 地址")
    return RedirectResponse(url=agent_card_well_known_path(agent_id), status_code=307)
