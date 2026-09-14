"""MCP Runner 会话审计写入。"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.exceptions import BadRequestError
from miles_exec.mcp.spec import RunSpec
from miles_portal.tenant.mcp.models import McpRunnerSession


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


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


#: 由 ``record_runner_session`` 计算注入，调用方不应自行传入。
_INJECTED_KWARGS = frozenset({"status", "duration_ms", "error_message"})


@asynccontextmanager
async def record_runner_session(
    write: Callable[..., Awaitable[None]],
    /,
    *common_args: Any,
    **common_kwargs: Any,
) -> AsyncIterator[None]:
    """把一段 Runner 调用包成「恰好写一条审计」：正常退出记 ``success``，``BadRequestError`` 记 ``error`` 后原样抛出。

    全部 Runner 调用点（脚本工具、技能脚本、STDIO 同步与试调用）都要求
    「无论成败都留痕且只留一条」。此前该约束由 4 处复制粘贴的 try/except
    维持，漏写 except 就会让失败调用不留审计；收敛到此处后成为结构性保证。

    - ``write``：``write_mcp_runner_session`` 或 ``write_script_runner_session``；
    - ``common_args`` / ``common_kwargs``：该写入函数除 ``status``/
      ``duration_ms``/``error_message`` 之外的固定实参，**原样转发**，故调用
      形式与直接调用写入函数一致（如 ``record_runner_session(write_fn, db,
      tenant_id=..., source=..., tool_name=...)``）。

    只捕获 ``BadRequestError``：其余异常视为程序缺陷，不加审计直接冒泡。
    """
    duplicated = _INJECTED_KWARGS & common_kwargs.keys()
    if duplicated:
        raise TypeError(f"{sorted(duplicated)} 由 record_runner_session 注入，不应由调用方传入")

    started = time.monotonic()
    try:
        yield
    except BadRequestError as exc:
        await write(
            *common_args,
            status="error",
            duration_ms=_elapsed_ms(started),
            error_message=exc.message,
            **common_kwargs,
        )
        raise
    else:
        await write(*common_args, status="success", duration_ms=_elapsed_ms(started), **common_kwargs)
