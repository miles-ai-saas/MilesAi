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

from miles_ai.rag.generate import retrieve_hits
from miles_common.exceptions import BadRequestError
from miles_core.tenant import TenantContext
from miles_core.url_security import validate_outbound_url
from miles_portal.tenant.compliance.services.pipeline import CompliancePipeline
from miles_portal.tenant.compliance.services.word_resolve import load_tenant_scan_words
from miles_portal.tenant.kb.services.embeddings import build_kb_retrieval_bindings
from miles_portal.tenant.skills.runtime import skill_read_reference, skill_run_script
from miles_portal.tenant.tools.builtins.calculator import safe_calculate
from miles_portal.tenant.tools.builtins.code_exec import DEFAULT_MAX_MEMORY_MB, DEFAULT_TIMEOUT_SEC, execute_code
from miles_portal.tenant.tools.builtins.generative import handle_generate_image, handle_generate_speech, handle_generate_video
from miles_portal.tenant.tools.builtins.web_search import search

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
    agent_id: UUID | None = None,
    **_: Any,
) -> dict:
    """知识库语义检索（多库）。

    知识库来源优先级：``kb_ids`` 列表 → 单个 ``kb_id`` → 智能体已绑定知识库
    （由对话装配注入 ``agent.config._bound_kb_ids``）。检索按各 KB 自身
    vector/hybrid/rerank 配置执行并全局排序，与线性 RAG / LangGraph 路径一致。
    """
    query = params.get("query") or params.get("q", "")
    if not query:
        raise BadRequestError("knowledge_search 需要 query 参数")

    bound_ids, bound_top_k = await _bound_kb_config(db, agent_id)
    kb_ids = _resolve_kb_ids(params) or bound_ids
    if not kb_ids:
        raise BadRequestError("knowledge_search 需要 kb_id / kb_ids，或智能体需绑定知识库")

    try:
        top_k = int(params.get("limit") or bound_top_k or 5)
    except (TypeError, ValueError):
        top_k = 5
    hits = await retrieve_hits(
        str(query),
        tenant_id=ctx.tenant_id,
        kb_ids=kb_ids,
        db=db,
        top_k=top_k,
        bindings=build_kb_retrieval_bindings(),
    )
    return {"hits": hits, "kb_ids": kb_ids, "hit_count": len(hits)}


def _resolve_kb_ids(params: dict) -> list[str]:
    """解析 ``kb_ids`` / ``kb_id`` 参数为字符串列表（去重、保序）。"""
    raw = params.get("kb_ids")
    if isinstance(raw, str):
        candidates: list[Any] = [p.strip() for p in raw.split(",")]
    elif isinstance(raw, (list, tuple)):
        candidates = list(raw)
    else:
        candidates = []
    single = params.get("kb_id")
    if single:
        candidates.append(single)
    out: list[str] = []
    for item in candidates:
        text = str(item).strip()
        if text and text not in out:
            out.append(text)
    return out


async def _bound_kb_config(db: AsyncSession, agent_id: UUID | None) -> tuple[list[str], int | None]:
    """读取智能体绑定知识库与默认条数。

    优先使用对话装配注入的 ``agent.config._bound_kb_*``；缺失（如子智能体、
    A2A 等跨会话调用）时回退到 DB 中智能体实际绑定的知识库。
    """
    if not agent_id:
        return [], None
    from sqlalchemy.orm import selectinload

    from miles_core.models.agent import Agent

    agent = await db.get(Agent, agent_id, options=[selectinload(Agent.knowledge_bases)])
    if not agent:
        return [], None
    cfg = agent.config if isinstance(agent.config, dict) else {}
    raw = cfg.get("_bound_kb_ids") or []
    if isinstance(raw, str):
        raw = [raw]
    kb_ids = [str(i) for i in raw if str(i).strip()]
    if not kb_ids:
        kb_ids = [str(kb.id) for kb in agent.knowledge_bases]
    try:
        top_k = int(cfg.get("_bound_kb_top_k")) if cfg.get("_bound_kb_top_k") else None
    except (TypeError, ValueError):
        top_k = None
    return kb_ids, top_k


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


async def handle_compliance_check_text(
    params: dict,
    *,
    db: AsyncSession,
    ctx: TenantContext,
    **_: Any,
) -> dict:
    """租户敏感词检测（只读）。

    复用 Agent 对话同一套词库与 ``CompliancePipeline``，但**不写 InterceptLog**：
    本工具是 Agent 主动自检，不等同于入出站拦截，不应污染拦截审计。
    未绑定/未启用词库时返回 ``scanning_enabled=False``。
    """
    text = params.get("text")
    if text is None:
        text = params.get("content") or params.get("query") or ""
    if not isinstance(text, str) or not text.strip():
        raise BadRequestError("compliance_check_text 需要 text 参数")

    words = await load_tenant_scan_words(db, ctx.tenant_id)
    if not words:
        return {
            "scanning_enabled": False,
            "blocked": False,
            "warned": False,
            "worst_action": None,
            "matches": [],
            "match_count": 0,
        }

    result = CompliancePipeline(words).scan(text)
    matches = [{"word": m.word, "action": m.action.value} for m in result.matches]
    return {
        "scanning_enabled": True,
        "blocked": result.has_block,
        "warned": result.has_warn,
        "worst_action": result.worst_action.value if result.worst_action else None,
        "matches": matches,
        "match_count": len(matches),
    }


async def handle_code_execution(params: dict, **_: Any) -> dict:
    """Runner 沙箱执行 Python；委托 ``code_exec.execute_code``。"""
    code = params.get("code") or ""
    timeout = int(params.get("timeout", DEFAULT_TIMEOUT_SEC))
    memory = int(params.get("memory", DEFAULT_MAX_MEMORY_MB))
    return await execute_code(code, timeout_sec=timeout, max_memory_mb=memory)


async def handle_run_flow_once(
    params: dict,
    *,
    db: AsyncSession,
    ctx: TenantContext,
    **_: Any,
) -> dict:
    """触发本租户已发布流程一次；委托 ``flow_once.run_published_flow_once``。"""
    from miles_portal.tenant.tools.services.flow_once import run_published_flow_once

    inputs = params.get("inputs")
    if not isinstance(inputs, dict):
        inputs = {}
    query = params.get("query")
    if query and "query" not in inputs:
        inputs["query"] = query
    return await run_published_flow_once(
        db,
        ctx,
        flow_id=params.get("flow_id"),
        inputs=inputs,
        timeout_sec=params.get("timeout_sec"),
    )


async def handle_invoke_tenant_hook(
    params: dict,
    *,
    db: AsyncSession,
    ctx: TenantContext,
    **_: Any,
) -> dict:
    """手动触发本租户已注册的 HTTP 钩子；委托 ``hook_once.run_registered_http_hooks``。"""
    from miles_portal.tenant.tools.services.hook_once import run_registered_http_hooks

    payload = params.get("payload")
    if not isinstance(payload, dict):
        payload = {}
    query = params.get("query")
    if query and "query" not in payload:
        payload["query"] = query
    return await run_registered_http_hooks(
        db,
        ctx,
        trigger=params.get("trigger"),
        scope=params.get("scope"),
        target_id=params.get("target_id"),
        payload=payload,
    )


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
    "compliance_check_text": handle_compliance_check_text,  # 租户敏感词自检（只读）
    "code_execution": handle_code_execution,  # Runner 沙箱
    "run_flow_once": handle_run_flow_once,  # 触发已发布流程（需确认）
    "invoke_tenant_hook": handle_invoke_tenant_hook,  # 触发已注册 HTTP 钩子（需确认）
    "generate_speech": handle_generate_speech,  # P2: CosyVoice
    "generate_video": handle_generate_video,
    "generate_image": handle_generate_image,
    "skill_read_reference": handle_skill_read_reference,
    "skill_run_script": handle_skill_run_script,
}
