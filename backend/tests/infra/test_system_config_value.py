"""``system_config_int``：``SystemConfig.value`` 的整数解析。

该配置由管理端按 key 直接写入、无 schema 约束（``SystemConfigUpsert.value`` 只要求是
dict），因此这里锁两件事：合法值照常解析；**非法值必须留下日志痕迹**——静默回落会让
「上限 / 开关」类配置在写配置的人不知情的情况下失效。
"""

import logging

import pytest

from miles_core.utils.config_value import system_config_int


def test_plain_int():
    assert system_config_int(50, default=10) == 50


def test_wrapped_value_dict():
    assert system_config_int({"value": 50}, default=10) == 50


def test_missing_config_returns_default_without_warning(caplog):
    """未配置是预期状态，不该告警。"""
    with caplog.at_level(logging.WARNING, logger="miles_core.utils.config_value"):
        assert system_config_int(None, default=0) == 0

    assert caplog.records == []


@pytest.mark.parametrize("bad", ["abc", "50MB", {"value": None}, {"value": "many"}, {}, [1]])
def test_unparseable_value_warns_and_falls_back(bad, caplog):
    """已配置但无法解析：回落 default（是否 fail-open 由调用方决定），但必须留痕。"""
    with caplog.at_level(logging.WARNING, logger="miles_core.utils.config_value"):
        assert system_config_int(bad, default=7) == 7

    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.WARNING


def test_numeric_string_is_accepted():
    """管理端可能把数字存成字符串，这是可解析的，不该告警。"""
    assert system_config_int({"value": "50"}, default=10) == 50


def test_minimum_clamps_low_values():
    assert system_config_int(0, default=10, minimum=1) == 1
    assert system_config_int(-5, default=10, minimum=1) == 1


def test_minimum_zero_keeps_zero_meaning_unlimited():
    """配额类配置用 ``minimum=0``：0 是合法的「不限」语义，不能被夹成 1。"""
    assert system_config_int(0, default=99, minimum=0) == 0
    assert system_config_int(-3, default=99, minimum=0) == 0
