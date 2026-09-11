"""MCP Runner 会话审计写入。"""

from __future__ import annotations

import hashlib
import json
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.tenant.mcp.models import McpRunnerSession
from app.tenant.mcp.runner.spec import RunSpec


def _args_digest(args: list[str]) -> str:
    raw = json.dumps(args, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


async def write_mcp_runner_session(
    db: AsyncSession,
    *,
    spec: RunSpec,
    status: str,
    duration_ms: int,
    exit_code: int | None = None,
    error_message: str | None = None,
    tool_name: str | None = None,
) -> None:
    """写入一次 MCP Runner 会话审计；args 仅存摘要，不落明文。"""
    row = McpRunnerSession(
        tenant_id=spec.tenant_id,
        service_id=spec.service_id,
        actor_user_id=spec.actor_user_id,
        purpose=spec.purpose,
        command=spec.command,
        args_digest=_args_digest(spec.args),
        status=status,
        exit_code=exit_code,
        duration_ms=duration_ms,
        error_message=(error_message or "")[:2000] or None,
        tool_name=tool_name,
    )
    db.add(row)
    await db.flush()


async def write_script_runner_session(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    tool_id: UUID | None,
    actor_user_id: UUID | None,
    source: str,
    status: str,
    duration_ms: int,
    exit_code: int | None = None,
    error_message: str | None = None,
    tool_name: str | None = None,
) -> None:
    """脚本工具 Runner 执行审计（无 MCP service_id）。"""
    digest = hashlib.sha256((source or "").encode()).hexdigest()[:32]
    row = McpRunnerSession(
        tenant_id=tenant_id,
        service_id=None,
        actor_user_id=actor_user_id,
        purpose="script_exec",
        command="python3",
        args_digest=digest,
        status=status,
        exit_code=exit_code,
        duration_ms=duration_ms,
        error_message=(error_message or "")[:2000] or None,
        tool_name=tool_name,
    )
    db.add(row)
    await db.flush()
