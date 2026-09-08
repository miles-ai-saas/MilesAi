"""内置工具 slug → handler 分发层。

``BUILTIN_HANDLERS`` 由 ``invoke_tool_with_context`` 按 slug 查找并调用。
各 handler 签名统一为 ``(params, *, db, ctx, ...) -> dict``，具体实现委托至
``code_exec`` / ``web_search`` / ``generative`` 等子模块。
"""

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError
from app.common.url_security import validate_outbound_url
from app.core.tenant import TenantContext
from app.infra.db import get_sync_db
from app.integrations.langchain.vectorstores import search_kb
from app.rag.load import load_kb_sync
from app.tenant.kb.services.embeddings import build_kb_retrieval_bindings
from app.tenant.skills.runtime import skill_read_reference, skill_run_script
from app.tenant.tools.builtins.calculator import safe_calculate
from app.tenant.tools.builtins.code_exec import DEFAULT_MAX_MEMORY_MB, DEFAULT_TIMEOUT_SEC, execute_code
from app.tenant.tools.builtins.generative import handle_generate_image, handle_generate_speech, handle_generate_video
from app.tenant.tools.builtins.web_search import search

BuiltinHandler = Callable[..., Awaitable[dict]]


async def handle_calculator(params: dict, **_: Any) -> dict:
    """安全计算数学表达式；委托 ``calculator.safe_calculate``。"""
    expr = params.get("expression") or params.get("expr") or params.get("query", "")
    if not expr:
        raise BadRequestError("calculator 需要 expression 参数")
    return {"result": safe_calculate(str(expr))}


async def handle_http_request(params: dict, **_: Any) -> dict:
    """发起出站 HTTP 请求；URL 经 ``validate_outbound_url`` 校验。"""
    url = params.get("url")
    if not url:
        raise BadRequestError("http_request 需要 url 参数")
    validate_outbound_url(str(url))
    method = str(params.get("method", "GET")).upper()
    async with httpx.AsyncClient(timeout=float(params.get("timeout", 10))) as client:
        resp = await client.request(method, url, json=params.get("json"), params=params.get("params"))
    return {"status_code": resp.status_code, "body": resp.text[:4000]}


async def handle_knowledge_search(
    params: dict,
    *,
    db: AsyncSession,
    ctx: TenantContext,
    **_: Any,
) -> dict:
    """知识库语义检索；同步加载 KB 后调用 ``search_kb``。"""
    query = params.get("query") or params.get("q", "")
    kb_id = params.get("kb_id")
    if not query:
        raise BadRequestError("knowledge_search 需要 query 参数")
    if not kb_id:
        raise BadRequestError("knowledge_search 需要 kb_id 参数")

    with get_sync_db() as sync_db:
        kb = load_kb_sync(sync_db, ctx.tenant_id, UUID(str(kb_id)))
        hits = search_kb(
            str(query),
            kb=kb,
            db=sync_db,
            limit=int(params.get("limit", 5)),
            bindings=build_kb_retrieval_bindings(),
        )
    return {"hits": hits}


async def handle_get_current_datetime(params: dict, **_: Any) -> dict:
    """返回指定 IANA 时区的当前 ISO 8601 时间。"""
    tz_name = params.get("timezone") or params.get("tz") or "UTC"
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
    """读取绑定技能包 references/assets 文本；委托 ``skill_read_reference``。"""
    return await skill_read_reference(db, ctx, params, bound_skill_id=bound_skill_id)


async def handle_web_search(params: dict, **_: Any) -> dict:
    """DuckDuckGo 网页搜索；委托 ``web_search.search``。"""
    query = params.get("query") or params.get("q", "")
    if not query:
        raise BadRequestError("web_search 需要 query 参数")
    max_results = int(params.get("max_results", 5))
    return search(query, max_results=max_results)


async def handle_code_execution(params: dict, **_: Any) -> dict:
    """Runner 沙箱执行 Python；委托 ``code_exec.execute_code``。"""
    code = params.get("code") or ""
    timeout = int(params.get("timeout", DEFAULT_TIMEOUT_SEC))
    memory = int(params.get("memory", DEFAULT_MAX_MEMORY_MB))
    return await execute_code(code, timeout_sec=timeout, max_memory_mb=memory)


async def handle_skill_run_script(
    params: dict,
    *,
    db: AsyncSession,
    ctx: TenantContext,
    bound_skill_id: UUID | None = None,
    actor_user_id: UUID | None = None,
    **_: Any,
) -> dict:
    """沙箱执行绑定技能包 scripts 脚本；委托 ``skill_run_script``。"""
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
    # P2: 内置工具扩展
    "web_search": handle_web_search,  # DuckDuckGo
    "code_execution": handle_code_execution,  # Runner 沙箱
    "generate_speech": handle_generate_speech,  # P2: CosyVoice
    "generate_video": handle_generate_video,
    "generate_image": handle_generate_image,
    "skill_read_reference": handle_skill_read_reference,
    "skill_run_script": handle_skill_run_script,
}
