"""``run_python_script`` 的失败面特征化测试。

既有覆盖只到「白名单 stdlib 可用」「未注入模块 NameError」「import 被拒」三条
成功/校验路径。本文件锁定其余分支：非 JSON 输出、崩溃退出码、超时、临时目录
清理、``params`` 归一与 UTF-8 透传——拆分重构前先钉住这些形态。
"""

from __future__ import annotations

import pytest

from miles_common.exceptions import BadRequestError
from miles_exec.sandbox import script_exec
from miles_exec.sandbox.script_exec import run_python_script

_ECHO_SCRIPT = """
def run(params):
    return {"echo": params.get("text"), "keys": sorted(params.keys())}
"""

_CRASH_SCRIPT = """
def run(params):
    raise ValueError("boom")
"""

_HANG_SCRIPT = """
def run(params):
    while True:
        pass
"""

_NO_RUN_SCRIPT = "x = 1\n"

_NON_JSON_SCRIPT = """
def run(params):
    print("not json at all")
    return {}
"""


def _leftovers(work_dir) -> list:  # noqa: ANN001
    return sorted(p.name for p in work_dir.iterdir())


# --- params 与编码 -----------------------------------------------------------


async def test_params_none_is_coerced_to_empty_object(tmp_path):
    result = await run_python_script(_ECHO_SCRIPT, None, work_dir=str(tmp_path))  # type: ignore[arg-type]

    assert result.ok, result.message
    assert result.data == {"echo": None, "keys": []}


async def test_params_are_passed_as_utf8_json(tmp_path):
    result = await run_python_script(_ECHO_SCRIPT, {"text": "中文"}, work_dir=str(tmp_path))

    assert result.ok, result.message
    assert result.data == {"echo": "中文", "keys": ["text"]}


# --- 输出不合法 -------------------------------------------------------------


async def test_non_json_stdout_reports_invalid_output(tmp_path):
    result = await run_python_script(_NON_JSON_SCRIPT, {}, work_dir=str(tmp_path))

    assert result.ok is False
    assert result.error_code == "INVALID_OUTPUT"
    assert "not json at all" in (result.message or "")
    assert result.exit_code == 0  # 脚本本身正常退出，只是输出不合约定


async def test_missing_run_function_is_rejected_by_validation(tmp_path):
    """缺 ``run`` 的脚本在校验阶段即被拦下，不会走到 bootstrap 的运行时检查。"""
    with pytest.raises(BadRequestError, match="须定义 run"):
        await run_python_script(_NO_RUN_SCRIPT, {}, work_dir=str(tmp_path))


# --- 崩溃与超时 -------------------------------------------------------------


async def test_script_exception_reports_exit_code_and_traceback(tmp_path):
    result = await run_python_script(_CRASH_SCRIPT, {}, work_dir=str(tmp_path))

    assert result.ok is False
    assert result.error_code == "PROCESS_CRASH"
    assert "boom" in (result.message or "")
    assert result.exit_code not in (0, None)


async def test_timeout_reports_runtime_timeout_and_kills_process(tmp_path):
    result = await run_python_script(_HANG_SCRIPT, {}, max_runtime_sec=1, work_dir=str(tmp_path))

    assert result.ok is False
    assert result.error_code == "RUNTIME_TIMEOUT"
    assert result.exit_code == -9
    assert "1s" in (result.message or "")


# --- 临时目录清理 -----------------------------------------------------------


@pytest.mark.parametrize(
    ("script", "kwargs"),
    [
        (_ECHO_SCRIPT, {}),
        (_CRASH_SCRIPT, {}),
        (_NON_JSON_SCRIPT, {}),
        (_HANG_SCRIPT, {"max_runtime_sec": 1}),
    ],
    ids=["success", "crash", "invalid-output", "timeout"],
)
async def test_work_dir_is_cleaned_up(tmp_path, script, kwargs):
    await run_python_script(script, {}, work_dir=str(tmp_path), **kwargs)

    assert _leftovers(tmp_path) == []


async def test_script_error_is_returned_not_raised(tmp_path, monkeypatch):
    """写盘失败等内部异常同样转成 ``SCRIPT_ERROR``，且仍走清理。"""

    def boom(tmpdir, source):  # noqa: ANN001, ARG001
        raise OSError("disk full")

    monkeypatch.setattr(script_exec, "_write_script_files", boom)

    result = await run_python_script(_ECHO_SCRIPT, {}, work_dir=str(tmp_path))

    assert result.ok is False
    assert result.error_code == "SCRIPT_ERROR"
    assert "disk full" in (result.message or "")
    assert result.exit_code is None  # 子进程尚未启动
    assert _leftovers(tmp_path) == []


async def test_validation_error_still_propagates(tmp_path):
    """源码校验失败属调用方错误，按既有契约直接抛。"""
    with pytest.raises(BadRequestError):
        await run_python_script("import os\n\ndef run(params):\n    return {}", {}, work_dir=str(tmp_path))
