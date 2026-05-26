"""
内置与自定义工具执行（含确认策略与调用日志）。

内置 ``knowledge_search`` 与 RAG 关系
----------------------------------
同步 ``search_kb`` → 单 KB 向量/混合检索（与 Agent ``_rag_chat`` 多 KB 路径独立）。

MCP 工具真调用在 ``tenant.mcp.client``；本模块不实现 MCP 协议。
"""

import ast
import operator as op
import time
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.url_security import validate_outbound_url
from app.integrations.langchain.vectorstores import search_kb
from app.common.exceptions import BadRequestError, NotFoundError
from app.core.tenant import TenantContext
from app.tenant.tools.builtin_registry import BUILTIN_SLUGS
from app.tenant.tools.confirmation import ToolConfirmationRequired, resolve_tool_meta
from app.tenant.tools.invocation_log import write_tool_invocation_log
from app.tenant.tools.models import Tool, ToolType
from app.core.config import get_settings
from app.tenant.mcp.runner.audit import write_script_runner_session
from app.tenant.mcp.runner.client import RunnerClient
from app.tenant.hooks.models import HookScope, HookTrigger
from app.tenant.hooks.services.runner import HookRunner
from app.tenant.tools.parameters import validate_tool_params
from app.tenant.tools.script_validate import validate_script_source
from app.core.soft_delete import is_marked_deleted

SCRIPT_RUNNER_DISABLED = (
    "脚本工具需要启用 MCP Runner（MCP_RUNNER_ENABLED=true），请联系管理员"
)


_SAFE_OPS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Pow: op.pow,
    ast.USub: op.neg,
}


def _eval_expr(node: ast.AST):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp):
        return _SAFE_OPS[type(node.op)](_eval_expr(node.left), _eval_expr(node.right))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return _SAFE_OPS[ast.USub](_eval_expr(node.operand))
    raise ValueError("不支持的表达式")


def safe_calculate(expression: str) -> float:
    tree = ast.parse(expression.strip(), mode="eval")
    return float(_eval_expr(tree.body))


def _apply_template(template: str, params: dict) -> str:
    out = template
    for k, v in params.items():
        out = out.replace(f"{{{{{k}}}}}", str(v))
    return out


async def invoke_builtin(
    name: str,
    params: dict,
    *,
    db: AsyncSession,
    ctx: TenantContext,
) -> dict:
    if name == "calculator":
        expr = params.get("expression") or params.get("expr") or params.get("query", "")
        if not expr:
            raise BadRequestError("calculator 需要 expression 参数")
        return {"result": safe_calculate(str(expr))}

    if name == "http_request":
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

    if name == "knowledge_search":
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

    if name == "get_current_datetime":
        from datetime import datetime
        from zoneinfo import ZoneInfo

        tz_name = params.get("timezone") or "UTC"
        try:
            tz = ZoneInfo(str(tz_name))
        except Exception as exc:
            raise BadRequestError(f"无效时区: {tz_name}") from exc
        now = datetime.now(tz)
        return {"datetime": now.isoformat(), "timezone": tz_name}

    raise BadRequestError(f"未知内置工具: {name}")


async def invoke_custom_http(tool: Tool, params: dict) -> dict:
    validated = validate_tool_params(tool.parameters or [], params)
    cfg = tool.config or {}
    url = _apply_template(str(cfg.get("url", "")), validated)
    if not url:
        raise BadRequestError("HTTP 工具未配置 url")
    validate_outbound_url(url)
    method = str(cfg.get("method", "POST")).upper()
    headers = {
        k: _apply_template(str(v), validated) for k, v in (cfg.get("headers") or {}).items()
    }
    timeout = float(cfg.get("timeout_sec", cfg.get("timeout", 15)))
    async with httpx.AsyncClient(timeout=timeout) as client:
        if method == "GET":
            resp = await client.get(url, params=validated, headers=headers)
        else:
            body_mode = cfg.get("body_mode", "json")
            kwargs: dict = {"headers": headers}
            if body_mode == "json":
                kwargs["json"] = validated
            resp = await client.request(method, url, **kwargs)
    text = resp.text[:4000]
    result: dict = {"status_code": resp.status_code, "body": text}
    path = cfg.get("response_path")
    if path and "application/json" in resp.headers.get("content-type", ""):
        try:
            data = resp.json()
            for part in str(path).split("."):
                data = data[part]
            result["extracted"] = data
        except Exception:
            pass
    return result


async def invoke_custom_script(
    db: AsyncSession,
    tool: Tool,
    params: dict,
    *,
    ctx: TenantContext,
    actor_user_id: UUID | None = None,
) -> dict:
    settings = get_settings()
    if not settings.mcp_runner_enabled:
        raise BadRequestError(SCRIPT_RUNNER_DISABLED)

    validated = validate_tool_params(tool.parameters or [], params)
    cfg = tool.config or {}
    source = validate_script_source(str(cfg.get("source") or ""))
    timeout_sec = min(max(int(cfg.get("timeout_sec") or 30), 1), 120)
    memory_mb = min(max(int(cfg.get("max_memory_mb") or 512), 128), 2048)

    started = time.monotonic()
    try:
        output = await RunnerClient().exec_script(
            tenant_id=ctx.tenant_id,
            source=source,
            params=validated,
            tool_id=tool.id,
            actor_user_id=actor_user_id,
            max_runtime_sec=timeout_sec,
            max_memory_mb=memory_mb,
        )
        duration_ms = int((time.monotonic() - started) * 1000)
        await write_script_runner_session(
            db,
            tenant_id=ctx.tenant_id,
            tool_id=tool.id,
            actor_user_id=actor_user_id,
            source=source,
            status="success",
            duration_ms=duration_ms,
            tool_name=tool.slug,
        )
        return output
    except BadRequestError as e:
        duration_ms = int((time.monotonic() - started) * 1000)
        await write_script_runner_session(
            db,
            tenant_id=ctx.tenant_id,
            tool_id=tool.id,
            actor_user_id=actor_user_id,
            source=source,
            status="error",
            duration_ms=duration_ms,
            error_message=e.message,
            tool_name=tool.slug,
        )
        raise


async def invoke_tool_by_name(
    db: AsyncSession,
    ctx: TenantContext,
    name: str,
    params: dict,
    *,
    tool_id: UUID | None = None,
) -> dict:
    """按 slug 执行；不含确认与日志（内部用）。"""
    if name in BUILTIN_SLUGS and not tool_id:
        return await invoke_builtin(name, params, db=db, ctx=ctx)

    if tool_id:
        tool = await db.get(Tool, tool_id)
    else:
        from sqlalchemy import select

        tool = await db.scalar(
            select(Tool).where(
                Tool.tenant_id == ctx.tenant_id,
                Tool.slug == name,
                Tool.is_active.is_(True),
            )
        )
    if not tool or is_marked_deleted(tool):
        raise NotFoundError("工具不存在")
    if tool.tool_type == ToolType.HTTP:
        return await invoke_custom_http(tool, params)
    if tool.tool_type == ToolType.SCRIPT:
        return await invoke_custom_script(
            db, tool, params, ctx=ctx, actor_user_id=ctx.user_id
        )
    raise BadRequestError(f"暂不支持执行工具类型: {tool.tool_type}")


async def invoke_tool_with_context(
    db: AsyncSession,
    ctx: TenantContext,
    name: str,
    params: dict,
    *,
    tool_id: UUID | None = None,
    confirmed: bool = False,
    actor_user_id: UUID | None = None,
    agent_id: UUID | None = None,
    invoke_source: str = "api",
) -> dict:
    """带确认策略与审计日志的工具调用入口。"""
    meta = await resolve_tool_meta(db, ctx, name, tool_id=tool_id)
    slug = meta["slug"]
    resolved_tool_id = meta.get("tool_id") or tool_id

    if meta["require_confirmation"] and not confirmed:
        await write_tool_invocation_log(
            db,
            tenant_id=ctx.tenant_id,
            tool_slug=slug,
            tool_id=resolved_tool_id,
            source=meta["source"],
            status="confirmation_required",
            params=params,
            actor_user_id=actor_user_id,
            agent_id=agent_id,
            invoke_source=invoke_source,
        )
        raise ToolConfirmationRequired(
            slug, meta["name"], meta.get("description"), params
        )

    tool_params = dict(params)
    hook_runner = HookRunner(db, ctx.tenant_id)
    tool_scope_id = resolved_tool_id
    hook_base = {
        "module": "tool_invoke",
        "tool_slug": slug,
        "tool_id": str(tool_scope_id) if tool_scope_id else None,
        "params": tool_params,
        "agent_id": str(agent_id) if agent_id else None,
        "invoke_source": invoke_source,
    }
    before = await hook_runner.run(
        HookTrigger.BEFORE_TOOL,
        HookScope.TOOL,
        tool_scope_id,
        hook_base,
    )
    tool_params = dict(before.payload.get("params", tool_params))

    started = time.monotonic()
    try:
        output = await invoke_tool_by_name(
            db, ctx, slug, tool_params, tool_id=resolved_tool_id
        )
        latency_ms = int((time.monotonic() - started) * 1000)
        await write_tool_invocation_log(
            db,
            tenant_id=ctx.tenant_id,
            tool_slug=slug,
            tool_id=resolved_tool_id,
            source=meta["source"],
            status="success",
            params=tool_params,
            output=output,
            latency_ms=latency_ms,
            actor_user_id=actor_user_id,
            agent_id=agent_id,
            invoke_source=invoke_source,
        )
        await hook_runner.run(
            HookTrigger.AFTER_TOOL,
            HookScope.TOOL,
            tool_scope_id,
            {
                **hook_base,
                "params": tool_params,
                "output": output,
                "status": "success",
                "latency_ms": latency_ms,
            },
        )
        return output
    except ToolConfirmationRequired:
        raise
    except Exception as exc:
        latency_ms = int((time.monotonic() - started) * 1000)
        await write_tool_invocation_log(
            db,
            tenant_id=ctx.tenant_id,
            tool_slug=slug,
            tool_id=resolved_tool_id,
            source=meta["source"],
            status="error",
            params=params,
            error_message=str(exc)[:2000],
            latency_ms=latency_ms,
            actor_user_id=actor_user_id,
            agent_id=agent_id,
            invoke_source=invoke_source,
        )
        raise
