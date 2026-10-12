"""RunSpec 校验单元测试。"""

from uuid import uuid4

import pytest

from miles_common.exceptions import BadRequestError
from miles_exec.mcp.spec import (
    NetworkMode,
    RunSpec,
    extract_npx_packages,
    normalize_npx_package_name,
    parse_npx_package_whitelist,
    validate_run_spec,
)


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


def test_validate_allows_letter_n_in_args():
    """字符类不得把字面 ``n`` 当成元字符（历史 ``\\\\n`` 误伤包名）。"""
    validate_run_spec(
        _base_spec(command="npx", args=["-y", "@modelcontextprotocol/server-memory"]),
    )


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


def test_normalize_npx_package_strips_version():
    assert normalize_npx_package_name("@modelcontextprotocol/server-memory@1.2.3") == (
        "@modelcontextprotocol/server-memory"
    )
    assert normalize_npx_package_name("left-pad@1.0.0") == "left-pad"


def test_extract_npx_packages_from_flags_and_positional():
    assert extract_npx_packages(["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]) == [
        "@modelcontextprotocol/server-filesystem"
    ]
    assert extract_npx_packages(["-p", "@scope/pkg", "--", "x"]) == ["@scope/pkg"]


def test_validate_npx_accepts_whitelisted_package():
    validate_run_spec(
        _base_spec(command="npx", args=["-y", "@modelcontextprotocol/server-memory"]),
    )


def test_validate_npx_rejects_unknown_package():
    with pytest.raises(BadRequestError, match="npx 包不在白名单"):
        validate_run_spec(_base_spec(command="npx", args=["-y", "evil-mcp-server"]))


def test_validate_npx_requires_package():
    with pytest.raises(BadRequestError, match="须指定 npm 包名"):
        validate_run_spec(_base_spec(command="npx", args=["-y"]))


def test_validate_npx_star_allows_any():
    validate_run_spec(
        _base_spec(command="npx", args=["-y", "any-pkg"]),
        npx_package_whitelist=frozenset({"*"}),
    )


def test_parse_npx_package_whitelist_empty_falls_back():
    allowed = parse_npx_package_whitelist("")
    assert "@modelcontextprotocol/server-filesystem" in allowed
