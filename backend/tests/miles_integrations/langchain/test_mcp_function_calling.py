"""MCP → 智能体 function calling：命名、schema、装配、元数据解析与执行分发。

均为纯函数/单测：DB 用假 ``execute``，MCP 执行入口 monkeypatch，不触网络。
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from miles_common.exceptions import BadRequestError
from miles_core.tenant import TenantContext
from miles_exec.mcp.tools import normalize_tools
from miles_integrations.langchain.toolkit.catalog import build_platform_tools
from miles_integrations.langchain.toolkit.naming import (
    MCP_FUNCTION_PREFIX,
    compose_mcp_tool_name,
    ident_collision,
    is_mcp_tool_name,
    select_agent_tools,
    service_ident,
)
from miles_integrations.langchain.toolkit.specs import McpToolSpec, json_schema_to_pydantic, mcp_param_alias
from miles_portal.tenant.mcp.models import McpService, McpStatus
from miles_portal.tenant.mcp.schemas.mcp import McpServiceCreate, McpServiceUpdate
from miles_portal.tenant.mcp.services.mcp import McpServiceManager
from miles_portal.tenant.tools.invoke import context as invoke_context
from miles_portal.tenant.tools.services import mcp_tools


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

    def scalars(self) -> _Result:
        return self

    def all(self) -> list:
        return self._rows


class _FakeDB:
    """仅实现测试路径用到的 DB 方法。"""

    def __init__(self, rows: list, *, get_row: object | None = None) -> None:
        self._rows = rows
        self._get_row = get_row
        self.added: list = []

    async def execute(self, _stmt) -> _Result:  # noqa: ANN001
        return _Result(self._rows)

    def add(self, row) -> None:  # noqa: ANN001
        self.added.append(row)

    async def flush(self) -> None:
        return None

    async def refresh(self, _row) -> None:  # noqa: ANN001
        return None

    async def get(self, _model, _pk) -> object | None:  # noqa: ANN001
        return self._get_row


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


# --- 服务 ident 唯一性（派发所依赖的不变量，由写入侧守住）---


def test_service_ident_collision_is_deterministic_not_probabilistic():
    """纯 ASCII 名走直通、不加摘要，故能**确定性地**撞上别人的 ident（不靠哈希运气）。

    这正是「同租户内 ident 唯一」不能交给 ``service_ident`` 自我保证的原因；守点在写入侧，
    见 ``test_create_service_guard_rejects_colliding_ident``。
    """
    victim = "MCP示例·知识检索"
    attacker = service_ident(victim)  # 把服务名起成对手的 ident 即可
    assert compose_mcp_tool_name(victim, "search") == compose_mcp_tool_name(attacker, "search")
    assert ident_collision(attacker, [victim]) == victim


def test_ident_collision_has_no_false_positive():
    assert ident_collision("github", ["gitlab"]) is None
    # 纯中文名清洗后都塌缩成 svc，仅靠 4 位摘要区分：摘要不同即不算冲突
    assert service_ident("知识检索") != service_ident("待同步")
    assert ident_collision("知识检索", ["待同步"]) is None
    # 同名不算冲突（更新场景由调用方按 id 排除自身）
    assert ident_collision("github", ["github"]) is None


async def test_create_service_rejects_colliding_ident():
    """走真实入口 ``create_service``：删掉那里的守卫调用本用例必须变红（避免同义反复）。"""
    db = _FakeDB(["github", "MCP示例·知识检索"])
    mgr = McpServiceManager(db, _ctx())
    await mgr._assert_name_available("gitlab")  # 不冲突 → 放行
    body = McpServiceCreate(name=service_ident("MCP示例·知识检索"), endpoint_url="https://example.com/mcp", transport="http")
    with pytest.raises(BadRequestError, match="工具标识"):
        await mgr.create_service(body)


async def test_update_service_rejects_colliding_ident_but_allows_self():
    """改名到冲突 ident 被拒；名字未变时不校验（否则存量冲突的服务无法再编辑）。"""
    ctx = _ctx()
    now = datetime.now(UTC)
    row = McpService(
        id=uuid4(),
        name="旧名",
        tenant_id=ctx.tenant_id,
        endpoint_url="https://example.com/mcp",
        transport="http",
        connection_config={},
        tools_cache=[],
        status=McpStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    db = _FakeDB(["MCP示例·知识检索"], get_row=row)
    mgr = McpServiceManager(db, ctx)

    with pytest.raises(BadRequestError, match="工具标识"):
        await mgr.update_service(row.id, McpServiceUpdate(name=service_ident("MCP示例·知识检索")))
    updated = await mgr.update_service(row.id, McpServiceUpdate(name="旧名"))
    assert updated.name == "旧名"


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
        source="mcp",
    )
    assert out == {"text": "ok"}
    assert calls == {"slug": "mcp__github__create_issue", "params": {"title": "t"}}


async def test_invoke_tool_by_name_rejects_unknown_source():
    """未知 ``source`` 必须报错，不得回落到自定义工具分支 —— 判据分歧要炸出来而不是被吞掉。"""
    with pytest.raises(BadRequestError, match="未知的工具种类"):
        await invoke_context.invoke_tool_by_name(
            object(),
            _ctx(),
            "anything",
            {},
            source="whatever",  # type: ignore[arg-type]
        )


async def test_invoke_tool_by_name_does_not_guess_kind_from_name(monkeypatch):
    """内置 slug 也必须按传入的 ``source`` 走：名字不再参与判种（旧实现会命中内置分支）。"""
    calls: dict = {}

    async def fake_invoke_builtin(slug, params, **kwargs) -> dict:  # noqa: ANN001
        calls.update({"slug": slug})
        return {"ok": True}

    monkeypatch.setattr(invoke_context, "invoke_builtin", fake_invoke_builtin)

    out = await invoke_context.invoke_tool_by_name(object(), _ctx(), "calculator", {}, source="builtin")
    assert out == {"ok": True}
    assert calls == {"slug": "calculator"}
