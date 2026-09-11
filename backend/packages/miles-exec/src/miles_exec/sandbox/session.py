"""Runner 子进程会话：execve、超时、MCP 协议。"""

from __future__ import annotations

import asyncio
import os
import resource
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from miles_common.exceptions import BadRequestError
from miles_exec.mcp.spec import RunSpec, validate_run_spec
from miles_exec.mcp.stdio import McpStdioClient


@dataclass
class SessionResult:
    """MCP 子进程会话执行结果。"""

    ok: bool  # 是否成功
    data: Any = None  # 成功时的返回载荷
    error_code: str | None = None  # 失败错误码（如 RUNTIME_TIMEOUT）
    message: str | None = None  # 失败说明
    duration_ms: int = 0  # 耗时（毫秒）
    exit_code: int | None = None  # 子进程退出码


def _build_env(spec: RunSpec) -> dict[str, str]:
    env = os.environ.copy()
    env.update(spec.env)
    env.setdefault("HOME", "/tmp")
    env.setdefault("TMPDIR", "/tmp")
    if spec.network_mode.value == "deny":
        env["MCP_RUNNER_NETWORK"] = "deny"
    return env


def _preexec(memory_mb: int) -> None:
    try:
        import signal

        os.setsid()
        mem_bytes = memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
        signal.signal(signal.SIGINT, signal.SIG_DFL)
    except Exception:
        pass


async def run_mcp_session(
    spec: RunSpec,
    handler: Callable[[McpStdioClient], Awaitable[Any]],
    *,
    command_whitelist: frozenset[str],
    work_dir: str = "/tmp",
) -> SessionResult:
    """启动 MCP 子进程并跑完 ``handler``：设置内存 / CPU 限额与独立进程组，超时或崩溃转为失败结果返回。"""
    validate_run_spec(spec, command_whitelist=command_whitelist)
    started = time.monotonic()
    proc: asyncio.subprocess.Process | None = None
    try:
        proc = await asyncio.create_subprocess_exec(
            spec.command,
            *spec.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=_build_env(spec),
            cwd=work_dir,
            preexec_fn=lambda: _preexec(spec.max_memory_mb),
        )
        assert proc.stdin and proc.stdout
        client = McpStdioClient(proc.stdin, proc.stdout)
        await asyncio.wait_for(client.initialize(), timeout=min(spec.max_runtime_sec, 30))
        data = await asyncio.wait_for(handler(client), timeout=spec.max_runtime_sec)
        await _terminate(proc)
        duration_ms = int((time.monotonic() - started) * 1000)
        return SessionResult(
            ok=True,
            data=data,
            duration_ms=duration_ms,
            exit_code=proc.returncode,
        )
    except asyncio.TimeoutError:
        duration_ms = int((time.monotonic() - started) * 1000)
        if proc:
            await _kill(proc)
        return SessionResult(
            ok=False,
            error_code="RUNTIME_TIMEOUT",
            message=f"MCP 会话超时（{spec.max_runtime_sec}s）",
            duration_ms=duration_ms,
            exit_code=-9,
        )
    except BadRequestError as e:
        duration_ms = int((time.monotonic() - started) * 1000)
        if proc:
            await _kill(proc)
        return SessionResult(
            ok=False,
            error_code="MCP_RPC_ERROR",
            message=e.message,
            duration_ms=duration_ms,
            exit_code=proc.returncode if proc else None,
        )
    except Exception as e:
        duration_ms = int((time.monotonic() - started) * 1000)
        stderr_text = ""
        if proc and proc.stderr:
            try:
                stderr_bytes = await asyncio.wait_for(proc.stderr.read(), timeout=1.0)
                stderr_text = stderr_bytes.decode("utf-8", errors="replace")[:500]
            except Exception:
                pass
        if proc:
            await _kill(proc)
        msg = str(e)
        if stderr_text:
            msg = f"{msg}; stderr: {stderr_text}"
        code = "PROCESS_CRASH" if proc and proc.returncode not in (0, None) else "MCP_RPC_ERROR"
        return SessionResult(
            ok=False,
            error_code=code,
            message=msg[:2000],
            duration_ms=duration_ms,
            exit_code=proc.returncode if proc else None,
        )


async def _terminate(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return
    proc.terminate()
    try:
        await asyncio.wait_for(proc.wait(), timeout=2.0)
    except asyncio.TimeoutError:
        await _kill(proc)


async def _kill(proc: asyncio.subprocess.Process) -> None:
    try:
        import signal

        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, OSError):
        proc.kill()
    try:
        await asyncio.wait_for(proc.wait(), timeout=3.0)
    except asyncio.TimeoutError:
        pass
