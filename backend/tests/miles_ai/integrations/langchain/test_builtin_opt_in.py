"""L2 opt-in 内置工具：仅在 config.tool_slugs 显式勾选时进入 function schema。"""

from __future__ import annotations

from miles_ai.integrations.langchain.toolkit.catalog import (
    build_platform_tools,
    get_platform_tools,
    select_opt_in_builtin_tools,
)

_OPT_IN = {"web_search", "code_execution", "compliance_check_text", "run_flow_once", "invoke_tenant_hook"}
_BASELINE = {"calculator", "http_request", "get_current_datetime", "knowledge_search"}


def test_no_opt_in_tool_without_whitelist():
    """tool_slugs 为空（= 全部）时不得默认放开 opt-in 工具。"""
    assert select_opt_in_builtin_tools({}) == []
    assert select_opt_in_builtin_tools(None) == []
    assert select_opt_in_builtin_tools({"tool_slugs": []}) == []


def test_opt_in_only_when_listed():
    tools = select_opt_in_builtin_tools({"tool_slugs": ["run_flow_once", "invoke_tenant_hook"]})
    assert {t.name for t in tools} == {"run_flow_once", "invoke_tenant_hook"}
    assert all(t.args_schema is not None for t in tools)


def test_opt_in_accepts_scalar_string():
    tools = select_opt_in_builtin_tools({"tool_slugs": "web_search"})
    assert [t.name for t in tools] == ["web_search"]


def test_baseline_tools_always_present():
    assert {t.name for t in get_platform_tools()} == _BASELINE


def test_build_platform_tools_does_not_leak_opt_in_by_default():
    names = {t.name for t in build_platform_tools({})}
    assert not (names & _OPT_IN)
    assert _BASELINE <= names


def test_build_platform_tools_adds_listed_opt_in():
    names = {t.name for t in build_platform_tools({"tool_slugs": ["invoke_tenant_hook"]})}
    assert "invoke_tenant_hook" in names
    # 其余 opt-in 仍不注入
    assert not (names & (_OPT_IN - {"invoke_tenant_hook"}))
