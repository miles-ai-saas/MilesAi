"""出站「允许内网」开关：命名、默认值与作用域。

该开关原名 ``MCP_ALLOW_PRIVATE_HOSTS``，但它实际已同时约束三条出站路径 ——
MCP 端点、HTTP 工具、技能包 Git 导入 —— 故改名为 ``OUTBOUND_ALLOW_PRIVATE_HOSTS``，
并**不保留旧名兼容**（用户裁决：不需要兼容）。本文件锁定该决定与两项默认姿态。

改名本身不涉及行为变更，但有两类**静默失效**值得长期设防：

1. **旧环境变量名失效** → 已把 ``MCP_ALLOW_PRIVATE_HOSTS`` 置为 ``false`` 收紧过
   安全的部署，升级后会静默回到默认放行（fail-open）。本次按用户决定接受该破坏性
   变更，故用测试显式记录「旧名已不生效」，避免后人误以为兼容仍在。
2. **字段名关键字构造被静默忽略** → pydantic 在字段带 ``validation_alias`` 时，用
   **字段名**传参会被忽略而不报错（实测 ``Settings(字段名=False)`` 返回 ``True``），
   同样是 fail-open。本字段刻意不加 alias，并保留一条守卫防止日后有人加回。
"""

from __future__ import annotations

import pytest

from miles_common.exceptions import BadRequestError
from miles_core.config import Settings, get_settings
from miles_core.url_security import validate_outbound_url

#: 改名前的环境变量名。已废弃，仅用于断言它不再生效。
_LEGACY_ENV = "MCP_ALLOW_PRIVATE_HOSTS"
_ENV = "OUTBOUND_ALLOW_PRIVATE_HOSTS"


def _settings(**overrides) -> Settings:
    """不读 .env，避免宿主环境干扰判定。"""
    return Settings(_env_file=None, **overrides)


@pytest.fixture
def clean_env(monkeypatch):
    """确保两个环境变量在用例内可控，并让 get_settings 缓存不跨用例串味。"""
    monkeypatch.delenv(_ENV, raising=False)
    monkeypatch.delenv(_LEGACY_ENV, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_default_allows_private_hosts():
    """默认放行内网（自托管连内网 MCP / 对象存储所需），本用例钉住该默认值。"""
    assert _settings().outbound_allow_private_hosts is True


def test_env_var_disables_private_hosts(monkeypatch, clean_env):
    monkeypatch.setenv(_ENV, "false")
    assert _settings().outbound_allow_private_hosts is False


def test_legacy_env_var_no_longer_has_effect(monkeypatch, clean_env):
    """旧名已不生效（决定不做兼容）。

    本用例是**刻意的破坏性变更记录**：若将来有人补回兼容，这条会失败，提醒同步
    文档与升级说明，而不是让兼容悄悄出现。
    """
    monkeypatch.setenv(_LEGACY_ENV, "false")
    assert _settings().outbound_allow_private_hosts is True


def test_field_name_construction_is_not_silently_ignored(clean_env):
    """用字段名关键字构造必须生效。

    若有人给该字段加 ``validation_alias`` 而忘记 ``populate_by_name=True``，
    ``Settings(outbound_allow_private_hosts=False)`` 会被静默忽略并返回 ``True``，
    即调用方以为已禁止内网、实际仍放行。
    """
    assert _settings(outbound_allow_private_hosts=False).outbound_allow_private_hosts is False
    assert _settings(outbound_allow_private_hosts=True).outbound_allow_private_hosts is True


def test_env_var_blocks_private_ranges_end_to_end(monkeypatch, clean_env):
    """端到端：置 false 后应真正拦住本机、内网与云元数据地址。"""
    monkeypatch.setenv(_ENV, "false")
    for url in ("http://127.0.0.1/api", "http://192.168.1.10/api", "http://169.254.169.254/latest/meta-data"):
        with pytest.raises(BadRequestError, match="不允许连接"):
            validate_outbound_url(url)


def test_default_still_allows_private_hosts_end_to_end(clean_env):
    """默认姿态端到端：放行内网（而非仅字段读对）。"""
    assert validate_outbound_url("http://127.0.0.1/api") == "http://127.0.0.1/api"
