"""A2A 对外暴露：Agent Card 发现端点与 JSON-RPC ``message/send`` 调用端点。

多租户寻址见 ``tenant.a2a.server`` 模块 docstring。鉴权：Card GET 公开（A2A 发现
约定，且平台自身的 ``fetch_agent_card`` 不带凭证），调用 POST 须带该智能体的
``X-API-Key``。协议级错误回 JSON-RPC 错误信封（HTTP 200），不套平台
``{code,message,data}`` 信封 —— 外部 A2A 客户端按 JSON-RPC 解析。
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.exceptions import NotFoundError
from miles_core.infra.db import get_db
from miles_core.tenant import TenantContext
from miles_portal.tenant.a2a.server import (
    PARSE_ERROR,
    agent_card_well_known_path,
    jsonrpc_error,
)
from miles_portal.tenant.a2a.services.server import (
    build_agent_card_by_id,
    handle_a2a_rpc,
    resolve_default_published_agent_id,
)
from miles_portal.tenant.agents.deps_api_auth import require_agent_api_key

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


@router.post("/a2a/agents/{agent_id}")
async def a2a_jsonrpc(
    agent_id: UUID,
    request: Request,
    ctx: TenantContext = Depends(require_agent_api_key),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """A2A JSON-RPC 端点（``message/send``）。请求体非 JSON 时回 -32700 信封。"""
    try:
        payload = await request.json()
    except ValueError:
        return JSONResponse(jsonrpc_error(None, PARSE_ERROR, "请求体不是合法 JSON"))
    return JSONResponse(await handle_a2a_rpc(db, ctx, agent_id, payload))


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
