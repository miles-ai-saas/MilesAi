"""MCP → 智能体 function calling：命名、schema、装配、元数据解析与执行分发。

均为纯函数/单测：DB 用假 ``execute``，MCP 执行入口 monkeypatch，不触网络。
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.core.tenant import TenantContext
from app.integrations.langchain.tools import (
    MCP_FUNCTION_PREFIX,
    McpToolSpec,
    build_platform_tools,
    compose_mcp_tool_name,
    is_mcp_tool_name,
    json_schema_to_pydantic,
    mcp_param_alias,
    select_agent_tools,
)
from app.exec.mcp.tools import normalize_tools
from app.tenant.tools.invoke import context as invoke_context
from app.tenant.tools.services import mcp_tools


def _ctx() -> TenantContext:
    return TenantContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        username="tester",
        is_superuser=False,
        permissions=frozenset(),
    )


def _service(name: str, tools: list[dict]) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), name=name, tools_cache=tools)


class _Result:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def scalars(self) -> "_Result":
        return self

    def all(self) -> list:
        return self._rows


class _FakeDB:
    """仅实现测试路径用到的 ``execute(...).scalars().all()``。"""

    def __init__(self, rows: list) -> None:
        self._rows = rows

    async def execute(self, _stmt) -> _Result:  # noqa: ANN001
        return _Result(self._rows)


# --- 命名 ---


def test_compose_mcp_tool_name_ascii():
    assert compose_mcp_tool_name("github", "create_issue") == "mcp__github__create_issue"
    assert is_mcp_tool_name("mcp__github__create_issue")
    assert not is_mcp_tool_name("calculator")


def test_compose_mcp_tool_name_chinese_services_do_not_collide():
    a = compose_mcp_tool_name("MCP示例·知识检索", "search")
    b = compose_mcp_tool_name("MCP示例·待同步", "search")
    assert a != b
    assert a.startswith(MCP_FUNCTION_PREFIX) and b.startswith(MCP_FUNCTION_PREFIX)


def test_compose_mcp_tool_name_is_stable_and_capped():
    name = compose_mcp_tool_name("x" * 100, "y" * 100)
    assert len(name) <= 64
    assert name == compose_mcp_tool_name("x" * 100, "y" * 100)


# --- tools_cache 规范化 ---


def test_normalize_tools_preserves_schema_and_annotations():
    out = normalize_tools(
        [
            {
                "name": "search",
                "description": "d",
                "inputSchema": {"type": "object", "properties": {"q": {"type": "string"}}},
                "annotations": {"readOnlyHint": True},
            }
        ]
    )
    assert out[0]["name"] == "search"
    assert out[0]["inputSchema"]["properties"]["q"]["type"] == "string"
    assert out[0]["annotations"] == {"readOnlyHint": True}


# --- JSON Schema → pydantic ---


def test_json_schema_to_pydantic_required_optional_enum():
    model = json_schema_to_pydantic(
        {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "q"},
                "limit": {"type": "integer", "default": 5},
                "mode": {"type": "string", "enum": ["a", "b"]},
            },
            "required": ["query"],
        }
    )
    assert model is not None
    schema = model.model_json_schema()
    assert set(schema["required"]) == {"query"}
    assert schema["properties"]["limit"]["default"] == 5
    assert schema["properties"]["mode"]["enum"] == ["a", "b"]


def test_json_schema_to_pydantic_none_when_empty():
    assert json_schema_to_pydantic(None) is None
    assert json_schema_to_pydantic({"type": "object", "properties": {}}) is None


def test_mcp_param_alias_only_lossy_keys():
    assert mcp_param_alias({"properties": {"file-path": {"type": "string"}, "ok": {"type": "string"}}}) == {"file_path": "file-path"}


# --- 装配 ---


async def test_load_mcp_tool_specs_builds_and_skips_placeholder():
    service = _service(
        "github",
        [
            {
                "name": "create_issue",
                "description": "创建 issue",
                "inputSchema": {"type": "object", "properties": {"title": {"type": "string"}}},
            },
            {"name": "github_placeholder", "description": "同步失败"},
        ],
    )
    specs = await mcp_tools.load_mcp_tool_specs(
        _FakeDB([service]),
        _ctx(),
        {"mcp_service_ids": [str(service.id)]},
    )
    assert [s.slug for s in specs] == ["mcp__github__create_issue"]
    assert specs[0].tool_name == "create_issue"
    assert specs[0].service_id == str(service.id)


async def test_load_mcp_tool_specs_empty_without_binding():
    assert await mcp_tools.load_mcp_tool_specs(_FakeDB([]), _ctx(), {}) == []


def test_build_platform_tools_includes_mcp_specs():
    spec = McpToolSpec(
        slug="mcp__github__create_issue",
        tool_name="create_issue",
        service_id="svc",
        service_name="github",
        description="d",
        input_schema={"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]},
    )
    tools = build_platform_tools({}, [], [spec])
    assert spec.slug in {t.name for t in tools}
    built = next(t for t in tools if t.name == spec.slug)
    assert built.args_schema.model_json_schema()["required"] == ["title"]


def test_select_agent_tools_keeps_mcp_but_filters_others():
    class _T:
        def __init__(self, name: str) -> None:
            self.name = name

    tools = [_T("calculator"), _T("weather"), _T("mcp__github__create_issue")]
    assert [t.name for t in select_agent_tools(tools, ["calculator"])] == [
        "calculator",
        "mcp__github__create_issue",
    ]
    assert [t.name for t in select_agent_tools(tools, None)] == [
        "calculator",
        "weather",
        "mcp__github__create_issue",
    ]


# --- 元数据解析与确认策略 ---


def test_mcp_tool_require_confirmation_policy():
    assert mcp_tools.mcp_tool_require_confirmation({"annotations": {"readOnlyHint": True}}) is False
    assert mcp_tools.mcp_tool_require_confirmation({"annotations": {"readOnlyHint": False}}) is True
    assert mcp_tools.mcp_tool_require_confirmation({}) is True
    assert mcp_tools.mcp_tool_require_confirmation({"require_confirmation": False}) is False


async def test_resolve_mcp_tool_meta(monkeypatch):
    service = _service(
        "github",
        [{"name": "create_issue", "description": "d", "annotations": {"readOnlyHint": True}}],
    )

    async def fake_services(_db, _ctx) -> list:
        return [service]

    monkeypatch.setattr(mcp_tools, "load_tenant_mcp_services", fake_services)

    slug = compose_mcp_tool_name("github", "create_issue")
    meta = await mcp_tools.resolve_mcp_tool_meta(object(), _ctx(), slug)
    assert meta is not None
    assert meta["source"] == "mcp"
    assert meta["mcp_service_id"] == service.id
    assert meta["mcp_tool_name"] == "create_issue"
    assert meta["require_confirmation"] is False
    assert await mcp_tools.resolve_mcp_tool_meta(object(), _ctx(), "calculator") is None


# --- 执行分发 ---


async def test_invoke_tool_by_name_dispatches_mcp(monkeypatch):
    calls: dict = {}

    async def fake_invoke_mcp_tool_by_slug(db, ctx, slug, params) -> dict:  # noqa: ANN001
        calls.update({"slug": slug, "params": params})
        return {"text": "ok"}

    monkeypatch.setattr(mcp_tools, "invoke_mcp_tool_by_slug", fake_invoke_mcp_tool_by_slug)

    out = await invoke_context.invoke_tool_by_name(
        object(),
        _ctx(),
        "mcp__github__create_issue",
        {"title": "t"},
    )
    assert out == {"text": "ok"}
    assert calls == {"slug": "mcp__github__create_issue", "params": {"title": "t"}}
