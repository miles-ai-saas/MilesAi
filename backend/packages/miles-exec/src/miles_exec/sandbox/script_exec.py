"""Runner 内 Python 脚本执行。

用户脚本禁止 ``import``，但 Runner 预注入 ``json`` / ``math`` / ``re`` /
``datetime`` 四个白名单模块（见 ``_BOOTSTRAP``），脚本可直接引用。
"""

from __future__ import annotations

import asyncio
import json
import os
import textwrap
import time
import uuid

from miles_exec.sandbox.session import SessionResult, _kill, _preexec
from miles_exec.sandbox.validate import validate_script_source

_BOOTSTRAP = textwrap.dedent(
    """
    import datetime
    import importlib.util
    import json
    import math
    import re
    import sys

    # 预注入白名单 stdlib：脚本禁止 import，常用模块由 Runner 直接提供。
    # 注入发生在 exec_module 之前，脚本自身的同名赋值仍以脚本为准。
    _STDLIB = {"json": json, "math": math, "re": re, "datetime": datetime}

    spec = importlib.util.spec_from_file_location("user_tool", "user_script.py")
    mod = importlib.util.module_from_spec(spec)
    for _name, _module in _STDLIB.items():
        setattr(mod, _name, _module)
    spec.loader.exec_module(mod)
    run = getattr(mod, "run", None)
    if not callable(run):
        raise RuntimeError("user_script.py 须定义 run(params)")
    params = json.loads(sys.stdin.read())
    result = run(params)
    if result is None:
        result = {}
    if not isinstance(result, dict):
        result = {"result": result}
    print(json.dumps(result, ensure_ascii=False))
    """
).strip()


async def run_python_script(
    source: str,
    params: dict,
    *,
    max_runtime_sec: int = 30,
    max_memory_mb: int = 512,
    work_dir: str = "/tmp",
) -> SessionResult:
    """在受限子进程中执行用户脚本：校验源码、注入白名单 stdlib，限制内存 / CPU / 超时，stdout 须输出 JSON。

    各类失败（超时、崩溃、输出非法）统一转为 ``SessionResult`` 返回，不向调用方抛异常。
    """
    validate_script_source(source)
    started = time.monotonic()
    proc: asyncio.subprocess.Process | None = None
    tmpdir = os.path.join(work_dir, f"script-{uuid.uuid4().hex}")
    os.makedirs(tmpdir, mode=0o700, exist_ok=True)
    try:
        script_path = os.path.join(tmpdir, "user_script.py")
        bootstrap_path = os.path.join(tmpdir, "bootstrap.py")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(source)
        with open(bootstrap_path, "w", encoding="utf-8") as f:
            f.write(_BOOTSTRAP)

        payload = json.dumps(params or {}, ensure_ascii=False).encode("utf-8")
        proc = await asyncio.create_subprocess_exec(
            "python3",
            bootstrap_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=tmpdir,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": tmpdir, "TMPDIR": tmpdir},
            preexec_fn=lambda: _preexec(max_memory_mb),
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=payload),
            timeout=max_runtime_sec,
        )
        duration_ms = int((time.monotonic() - started) * 1000)
        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace")[:2000]
            return SessionResult(
                ok=False,
                error_code="PROCESS_CRASH",
                message=err or f"脚本退出码 {proc.returncode}",
                duration_ms=duration_ms,
                exit_code=proc.returncode,
            )
        text = stdout.decode("utf-8", errors="replace").strip()
        try:
            data = json.loads(text) if text else {}
        except json.JSONDecodeError:
            return SessionResult(
                ok=False,
                error_code="INVALID_OUTPUT",
                message=f"脚本须向 stdout 输出 JSON，收到: {text[:200]}",
                duration_ms=duration_ms,
                exit_code=proc.returncode,
            )
        if not isinstance(data, dict):
            data = {"result": data}
        return SessionResult(
            ok=True,
            data=data,
            duration_ms=duration_ms,
            exit_code=proc.returncode,
        )
    except TimeoutError:
        duration_ms = int((time.monotonic() - started) * 1000)
        if proc:
            await _kill(proc)
        return SessionResult(
            ok=False,
            error_code="RUNTIME_TIMEOUT",
            message=f"脚本执行超时（{max_runtime_sec}s）",
            duration_ms=duration_ms,
            exit_code=-9,
        )
    except Exception as e:
        duration_ms = int((time.monotonic() - started) * 1000)
        if proc:
            await _kill(proc)
        return SessionResult(
            ok=False,
            error_code="SCRIPT_ERROR",
            message=str(e)[:2000],
            duration_ms=duration_ms,
            exit_code=proc.returncode if proc else None,
        )
    finally:
        try:
            for name in ("user_script.py", "bootstrap.py"):
                path = os.path.join(tmpdir, name)
                if os.path.exists(path):
                    os.remove(path)
            os.rmdir(tmpdir)
        except OSError:
            pass
