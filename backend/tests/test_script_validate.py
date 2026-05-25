import pytest

from app.common.exceptions import BadRequestError
from app.tenant.tools.script_validate import validate_script_source


def test_validate_script_accepts_run():
    src = validate_script_source(
        'def run(params: dict) -> dict:\n    return {"ok": True, "n": len(params)}'
    )
    assert "def run" in src


def test_validate_script_rejects_missing_run():
    with pytest.raises(BadRequestError, match="run\\(params\\)"):
        validate_script_source("def helper():\n    pass")


def test_validate_script_rejects_import():
    with pytest.raises(BadRequestError, match="import"):
        validate_script_source(
            "import os\n\ndef run(params: dict) -> dict:\n    return {}"
        )


def test_validate_script_rejects_eval():
    with pytest.raises(BadRequestError):
        validate_script_source(
            'def run(params: dict) -> dict:\n    return {"x": eval("1+1")}'
        )
