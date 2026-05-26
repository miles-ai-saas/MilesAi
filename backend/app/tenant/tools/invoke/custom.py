"""自定义 HTTP / 脚本工具执行（``invoke_custom_http`` / ``invoke_custom_script``）。"""

import time
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError
from app.common.url_security import validate_outbound_url
from app.core.config import get_settings
from app.core.tenant import TenantContext
from app.tenant.mcp.runner.audit import write_script_runner_session
from app.tenant.mcp.runner.client import RunnerClient
from app.tenant.tools.builtins.template import apply_template
from app.tenant.tools.models import Tool
from app.tenant.tools.parameters import validate_tool_params
from app.tenant.tools.script_validate import validate_script_source

SCRIPT_RUNNER_DISABLED = (
    "脚本工具需要启用 MCP Runner（MCP_RUNNER_ENABLED=true），请联系管理员"
)


async def invoke_custom_http(tool: Tool, params: dict) -> dict:
    """执行租户配置的 HTTP 工具。"""
    validated = validate_tool_params(tool.parameters or [], params)
    cfg = tool.config or {}
    url = apply_template(str(cfg.get("url", "")), validated)
    if not url:
        raise BadRequestError("HTTP 工具未配置 url")
    validate_outbound_url(url)
    method = str(cfg.get("method", "POST")).upper()
    headers = {
        k: apply_template(str(v), validated) for k, v in (cfg.get("headers") or {}).items()
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
    """经 MCP Runner 执行脚本工具。"""
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
