"""RunSpec 校验单元测试。"""

from uuid import uuid4

import pytest

from miles_common.exceptions import BadRequestError
from miles_exec.mcp.spec import NetworkMode, RunSpec, validate_run_spec


def _base_spec(**kwargs) -> RunSpec:
    defaults = {
        "tenant_id": uuid4(),
        "service_id": uuid4(),
        "command": "node",
        "args": ["-v"],
    }
    defaults.update(kwargs)
    return RunSpec(**defaults)


def test_validate_accepts_whitelisted_command():
    validate_run_spec(_base_spec(command="python3"))


def test_validate_rejects_unknown_command():
    with pytest.raises(BadRequestError, match="白名单"):
        validate_run_spec(_base_spec(command="bash"))


def test_validate_rejects_shell_metachar_in_args():
    with pytest.raises(ValueError, match="shell"):
        _base_spec(args=["-c", "rm; -rf /"])


def test_validate_rejects_path_traversal_in_args():
    with pytest.raises(ValueError, match="路径"):
        _base_spec(args=["../../etc/passwd"])


def test_validate_rejects_invalid_env_key():
    with pytest.raises(BadRequestError, match="环境变量"):
        validate_run_spec(_base_spec(env={"bad-key": "x"}))


def test_validate_rejects_custom_cwd():
    with pytest.raises(BadRequestError, match="cwd"):
        validate_run_spec(_base_spec(cwd="/tmp"))


def test_network_mode_enum():
    spec = _base_spec(network_mode=NetworkMode.DENY)
    assert spec.network_mode == NetworkMode.DENY
