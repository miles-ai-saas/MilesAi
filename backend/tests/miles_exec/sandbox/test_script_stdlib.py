"""Runner 预注入 whitelist stdlib：脚本禁 import 仍可用 json/re/math/datetime。"""

from __future__ import annotations

import pytest

from miles_common.exceptions import BadRequestError
from miles_exec.sandbox.script_exec import run_python_script

_STDLIB_SCRIPT = """
def run(params):
    return {
        "digits": re.findall(r"\\d+", params["text"]),
        "rounded": math.floor(params["value"]),
        "payload": json.loads(json.dumps({"ok": True})),
        "year": datetime.datetime(2026, 1, 1).year,
    }
"""

_UNINJECTED_SCRIPT = """
def run(params):
    return {"cwd": os.getcwd()}
"""


async def test_whitelisted_stdlib_is_available(tmp_path):
    result = await run_python_script(
        _STDLIB_SCRIPT,
        {"text": "a1b22", "value": 3.7},
        work_dir=str(tmp_path),
    )
    assert result.ok, result.message
    assert result.data == {
        "digits": ["1", "22"],
        "rounded": 3,
        "payload": {"ok": True},
        "year": 2026,
    }


async def test_non_whitelisted_module_is_not_injected(tmp_path):
    result = await run_python_script(_UNINJECTED_SCRIPT, {}, work_dir=str(tmp_path))
    assert result.ok is False
    assert result.error_code == "PROCESS_CRASH"
    assert "NameError" in (result.message or "")


async def test_import_is_still_rejected():
    with pytest.raises(BadRequestError):
        await run_python_script("import os\n\ndef run(params):\n    return {}", {}, work_dir="/tmp")
