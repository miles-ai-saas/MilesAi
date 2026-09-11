"""MCP Runner HTTP 服务（/runner/v1）。"""

from __future__ import annotations

import os
from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from miles_exec.mcp.rpc import normalize_tool_call_result
from miles_exec.mcp.spec import RunSpec, validate_run_spec
from miles_exec.mcp.tools import normalize_tools
from miles_exec.sandbox.script_exec import run_python_script
from miles_exec.sandbox.session import SessionResult, run_mcp_session
from miles_exec.sandbox.validate import validate_script_source
from miles_runner.limits import RunnerLimits
from miles_runner.settings import get_runner_settings

settings = get_runner_settings()
limits = RunnerLimits(
    max_global=int(os.environ.get("MCP_RUNNER_MAX_CONCURRENT", "20")),
    max_per_tenant=settings.mcp_runner_max_concurrent_per_tenant,
)
WORK_DIR = os.environ.get("MCP_RUNNER_WORK_DIR", "/tmp")
COMMAND_WHITELIST = settings.mcp_runner_command_whitelist_set

app = FastAPI(title="MilesAI MCP Runner", docs_url=None, redoc_url=None)


def _verify_token(x_runner_token: str | None = Header(default=None, alias="X-Runner-Token")) -> None:
    expected = settings.mcp_runner_token
    if not expected:
        raise HTTPException(status_code=503, detail="Runner token 未配置")
    if x_runner_token != expected:
        raise HTTPException(status_code=401, detail="Runner token 无效")


# MCP 会话请求：RunSpec 与可选连接配置。
class McpSessionRequest(BaseModel):
    run_spec: RunSpec
    connection_config: dict = Field(default_factory=dict)


# 会话执行元信息：耗时（毫秒）与子进程退出码。
class SessionMeta(BaseModel):
    duration_ms: int
    exit_code: int | None = None


# ``tools/list`` 响应：工具列表或错误码 / 说明。
class ListToolsResponse(BaseModel):
    ok: bool
    tools: list[dict] = Field(default_factory=list)
    session: SessionMeta | None = None
    error_code: str | None = None
    message: str | None = None


# ``tools/call`` 请求：在会话请求上追加工具名与参数。
class CallToolRequest(McpSessionRequest):
    tool_name: str
    arguments: dict = Field(default_factory=dict)


# ``tools/call`` 响应：工具输出或错误码 / 说明。
class CallToolResponse(BaseModel):
    ok: bool
    output: dict | None = None
    session: SessionMeta | None = None
    error_code: str | None = None
    message: str | None = None


# 脚本执行请求：源码、参数与运行时 / 内存上限。
class ScriptExecRequest(BaseModel):
    tenant_id: UUID
    tool_id: UUID | None = None
    actor_user_id: UUID | None = None
    source: str
    params: dict = Field(default_factory=dict)
    max_runtime_sec: int = 30
    max_memory_mb: int = 512


# 脚本执行响应：输出或错误码 / 说明。
class ScriptExecResponse(BaseModel):
    ok: bool
    output: dict | None = None
    session: SessionMeta | None = None
    error_code: str | None = None
    message: str | None = None


def _session_meta(result: SessionResult) -> SessionMeta:
    return SessionMeta(duration_ms=result.duration_ms, exit_code=result.exit_code)


def _error_response(result: SessionResult) -> dict[str, Any]:
    return {
        "ok": False,
        "error_code": result.error_code,
        "message": result.message,
        "session": _session_meta(result).model_dump(),
    }


@app.get("/health")
async def health() -> dict[str, str]:
    """服务存活探针。"""
    return {"status": "ok"}


@app.get("/runner/v1/health")
async def runner_health() -> dict[str, str]:
    """Runner 版本化健康检查（供探测是否已升级到 ``/runner/v1`` 路径）。"""
    return {"status": "ok"}


@app.post("/runner/v1/sessions/mcp/list-tools", response_model=ListToolsResponse)
async def list_tools(
    body: McpSessionRequest,
    _: None = Depends(_verify_token),
) -> ListToolsResponse:
    """在沙箱会话中执行 MCP ``tools/list``；spec 非法时返回 ``INVALID_SPEC``。"""
    spec = body.run_spec
    try:
        validate_run_spec(spec, command_whitelist=COMMAND_WHITELIST)
    except Exception as e:
        return ListToolsResponse(ok=False, error_code="INVALID_SPEC", message=str(e))

    await limits.acquire(spec.tenant_id)
    try:

        async def handler(client):
            raw = await client.request("tools/list", {})
            return normalize_tools(raw if isinstance(raw, (list, dict)) else [])

        result = await run_mcp_session(
            spec,
            handler,
            command_whitelist=COMMAND_WHITELIST,
            work_dir=WORK_DIR,
        )
    finally:
        limits.release(spec.tenant_id)

    if not result.ok:
        return ListToolsResponse(**_error_response(result))
    return ListToolsResponse(
        ok=True,
        tools=result.data or [],
        session=_session_meta(result),
    )


@app.post("/runner/v1/sessions/mcp/call-tool", response_model=CallToolResponse)
async def call_tool(
    body: CallToolRequest,
    _: None = Depends(_verify_token),
) -> CallToolResponse:
    """在沙箱会话中执行 MCP ``tools/call``；spec 非法时返回 ``INVALID_SPEC``。"""
    spec = body.run_spec
    spec.purpose = "mcp_invoke"
    try:
        validate_run_spec(spec, command_whitelist=COMMAND_WHITELIST)
    except Exception as e:
        return CallToolResponse(ok=False, error_code="INVALID_SPEC", message=str(e))

    await limits.acquire(spec.tenant_id)
    try:
        tool_name = body.tool_name
        arguments = body.arguments or {}

        async def handler(client):
            raw = await client.request(
                "tools/call",
                {"name": tool_name, "arguments": arguments},
            )
            return normalize_tool_call_result(raw)

        result = await run_mcp_session(
            spec,
            handler,
            command_whitelist=COMMAND_WHITELIST,
            work_dir=WORK_DIR,
        )
    finally:
        limits.release(spec.tenant_id)

    if not result.ok:
        return CallToolResponse(**_error_response(result))
    return CallToolResponse(
        ok=True,
        output=result.data,
        session=_session_meta(result),
    )


@app.post("/runner/v1/sessions/script/exec", response_model=ScriptExecResponse)
async def exec_script(
    body: ScriptExecRequest,
    _: None = Depends(_verify_token),
) -> ScriptExecResponse:
    """在沙箱中执行租户 Python 脚本；源码非法返回 ``INVALID_SCRIPT``，运行时 / 内存夹取到安全区间。"""
    try:
        validate_script_source(body.source)
    except Exception as e:
        return ScriptExecResponse(ok=False, error_code="INVALID_SCRIPT", message=str(e))

    await limits.acquire(body.tenant_id)
    try:
        result = await run_python_script(
            body.source,
            body.params or {},
            max_runtime_sec=min(max(body.max_runtime_sec, 1), 120),
            max_memory_mb=min(max(body.max_memory_mb, 128), 2048),
            work_dir=WORK_DIR,
        )
    finally:
        limits.release(body.tenant_id)

    if not result.ok:
        return ScriptExecResponse(**_error_response(result))
    return ScriptExecResponse(
        ok=True,
        output=result.data if isinstance(result.data, dict) else {"result": result.data},
        session=_session_meta(result),
    )
