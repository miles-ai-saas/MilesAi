"""内置工具 slug → handler。"""

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError
from app.common.url_security import validate_outbound_url
from app.core.tenant import TenantContext
from app.integrations.langchain.vectorstores import search_kb
from app.tenant.tools.builtins.calculator import safe_calculate
from app.tenant.tools.builtins.generative import handle_generate_image, handle_generate_video

BuiltinHandler = Callable[..., Awaitable[dict]]


async def handle_calculator(params: dict, **_: Any) -> dict:
    expr = params.get("expression") or params.get("expr") or params.get("query", "")
    if not expr:
        raise BadRequestError("calculator 需要 expression 参数")
    return {"result": safe_calculate(str(expr))}


async def handle_http_request(params: dict, **_: Any) -> dict:
    url = params.get("url")
    if not url:
        raise BadRequestError("http_request 需要 url 参数")
    validate_outbound_url(str(url))
    method = str(params.get("method", "GET")).upper()
    async with httpx.AsyncClient(timeout=float(params.get("timeout", 10))) as client:
        resp = await client.request(
            method, url, json=params.get("json"), params=params.get("params")
        )
    return {"status_code": resp.status_code, "body": resp.text[:4000]}


async def handle_knowledge_search(
    params: dict,
    *,
    db: AsyncSession,
    ctx: TenantContext,
    **_: Any,
) -> dict:
    query = params.get("query") or params.get("q", "")
    kb_id = params.get("kb_id")
    if not query:
        raise BadRequestError("knowledge_search 需要 query 参数")
    if not kb_id:
        raise BadRequestError("knowledge_search 需要 kb_id 参数")
    from app.infra.db import get_sync_db
    from app.rag.load import load_kb_sync

    with get_sync_db() as sync_db:
        kb = load_kb_sync(sync_db, ctx.tenant_id, UUID(str(kb_id)))
        hits = search_kb(str(query), kb=kb, db=sync_db, limit=int(params.get("limit", 5)))
    return {"hits": hits}


async def handle_get_current_datetime(params: dict, **_: Any) -> dict:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    tz_name = params.get("timezone") or "UTC"
    try:
        tz = ZoneInfo(str(tz_name))
    except Exception as exc:
        raise BadRequestError(f"无效时区: {tz_name}") from exc
    now = datetime.now(tz)
    return {"datetime": now.isoformat(), "timezone": tz_name}


async def handle_skill_read_reference(
    params: dict,
    *,
    db: AsyncSession,
    ctx: TenantContext,
    bound_skill_id: UUID | None = None,
    **_: Any,
) -> dict:
    from app.tenant.skills.runtime import skill_read_reference

    return await skill_read_reference(db, ctx, params, bound_skill_id=bound_skill_id)


async def handle_skill_run_script(
    params: dict,
    *,
    db: AsyncSession,
    ctx: TenantContext,
    bound_skill_id: UUID | None = None,
    actor_user_id: UUID | None = None,
    **_: Any,
) -> dict:
    from app.tenant.skills.runtime import skill_run_script

    return await skill_run_script(
        db,
        ctx,
        params,
        bound_skill_id=bound_skill_id,
        actor_user_id=actor_user_id or ctx.user_id,
    )


BUILTIN_HANDLERS: dict[str, BuiltinHandler] = {
    "calculator": handle_calculator,
    "http_request": handle_http_request,
    "knowledge_search": handle_knowledge_search,
    "get_current_datetime": handle_get_current_datetime,
    "generate_video": handle_generate_video,
    "generate_image": handle_generate_image,
    "skill_read_reference": handle_skill_read_reference,
    "skill_run_script": handle_skill_run_script,
}
