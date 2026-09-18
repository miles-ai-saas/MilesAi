"""内置 code_execution 工具：Runner 沙箱执行 Python 代码片段。

将用户输入的 Python 代码包装为 ``run(params)`` 函数，
通过 ``miles_exec.sandbox.script_exec.run_python_script`` 在隔离子进程中执行。
限制：30s 超时、256MB 内存、8000 字符 stdout 截断。
"""

from miles_common.exceptions import BadRequestError
from miles_exec.sandbox.script_exec import run_python_script

DEFAULT_TIMEOUT_SEC = 30
DEFAULT_MAX_MEMORY_MB = 256


async def execute_code(
    code: str,
    *,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    max_memory_mb: int = DEFAULT_MAX_MEMORY_MB,
) -> dict:
    """在 Runner 沙箱中执行 Python 代码片段，返回 stdout 与退出码。"""
    if not code or not code.strip():
        raise BadRequestError("code_execution 需要 code 参数")

    wrapper = f"""
def run(params):
{chr(10).join("    " + line for line in code.strip().splitlines())}
"""
    try:
        result = await run_python_script(
            wrapper,
            params={},
            max_runtime_sec=min(timeout_sec, 120),
            max_memory_mb=min(max_memory_mb, 512),
        )
    except TimeoutError:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"执行超时（{timeout_sec}s）",
        }
    except Exception as exc:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": str(exc),
        }

    return {
        "exit_code": result.exit_code,
        "stdout": (result.stdout or "")[:8000],
        "stderr": (result.stderr or "")[:2000],
    }
