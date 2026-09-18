"""多技能绑定：``agent.config`` 同时支持 ``skill_ids`` 列表与旧版 ``skill_package_id``。

覆盖四层：
1. 纯函数 ``bound_skill_ids`` 的读取/去重/脏数据容忍；
2. ``build_platform_tools`` 在任一形态下都挂载 ``skill_*`` 工具；
3. 运行时选包 ``resolve_skill_for_tool``：显式参数 > 绑定集合，多绑定必须消歧；
4. Prompt 注入：为每个绑定技能注入独立块（带 slug，供多绑定时传给工具）。
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from miles_ai.integrations.langchain.toolkit import catalog as lc_tools
from miles_ai.integrations.langchain.toolkit.catalog import bound_skill_ids
from miles_common.exceptions import BadRequestError
from miles_core.tenant import TenantContext
from miles_portal.tenant.agents.services import context as agent_context_mod
from miles_portal.tenant.agents.services.context import build_skill_mcp_prompt_block
from miles_portal.tenant.skills import runtime as runtime_mod
from miles_portal.tenant.skills.runtime import resolve_skill_for_tool
from miles_portal.tenant.tools.invoke import context as invoke_context_mod


def _ctx(tenant_id):
    return TenantContext(
        user_id=uuid4(),
        tenant_id=tenant_id,
        username="tester",
        is_superuser=True,
        permissions=frozenset(),
    )


# --- 1. bound_skill_ids -----------------------------------------------------


def test_bound_skill_ids_reads_list_and_legacy_single():
    a, b = str(uuid4()), str(uuid4())
    assert bound_skill_ids({"skill_ids": [a, b]}) == [a, b]
    # 旧版单值键仍被读取（向后兼容既有智能体）
    assert bound_skill_ids({"skill_package_id": a}) == [a]
    # 两键并存：合并去重，列表形态在前
    assert bound_skill_ids({"skill_ids": [a], "skill_package_id": b}) == [a, b]
    assert bound_skill_ids({"skill_ids": [a], "skill_package_id": a}) == [a]


def test_bound_skill_ids_tolerates_junk():
    a = str(uuid4())
    assert bound_skill_ids(None) == []
    assert bound_skill_ids({}) == []
    assert bound_skill_ids({"skill_ids": "not-actually-a-list"}) == ["not-actually-a-list"]
    assert bound_skill_ids({"skill_ids": [None, "", "  ", a]}) == [a]
    assert bound_skill_ids({"skill_ids": []}) == []


# --- 2. 装配 ----------------------------------------------------------------


def test_build_platform_tools_includes_skill_tools_for_list_form():
    names = {t.name for t in lc_tools.build_platform_tools({"skill_ids": [str(uuid4())]}, [])}
    assert "skill_read_reference" in names
    assert "skill_run_script" in names


def test_build_platform_tools_excludes_skill_tools_when_unbound():
    names = {t.name for t in lc_tools.build_platform_tools({"skill_ids": []}, [])}
    assert "skill_read_reference" not in names


# --- 3. 运行时选包 ----------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_bound_skill_ids_from_agent_merges_list_and_legacy():
    a, b = uuid4(), uuid4()

    class _Db:
        def __init__(self, cfg):
            self._cfg = cfg

        async def get(self, _model, _id):  # noqa: ANN001
            return SimpleNamespace(config=self._cfg)

    async def ids(cfg):
        return await invoke_context_mod.resolve_bound_skill_ids_from_agent(_Db(cfg), uuid4())

    assert await ids({"skill_ids": [str(a), str(b)]}) == [a, b]
    assert await ids({"skill_package_id": str(a)}) == [a]
    # 非 UUID 项跳过，合法项照常生效
    assert await ids({"skill_ids": ["not-a-uuid", str(a)]}) == [a]
    assert await ids({}) == []
    assert await invoke_context_mod.resolve_bound_skill_ids_from_agent(_Db({}), None) == []


@pytest.mark.asyncio
async def test_resolve_prefers_explicit_params_then_single_binding(monkeypatch):
    calls: list[tuple[str | None, str | None]] = []

    async def _resolve(db, ctx, *, skill_package_id=None, skill_slug=None):  # noqa: ANN001, ARG001
        calls.append((str(skill_package_id) if skill_package_id else None, skill_slug))
        return SimpleNamespace(slug=skill_slug or "resolved")

    monkeypatch.setattr(runtime_mod, "resolve_bound_skill", _resolve)
    ctx = _ctx(uuid4())
    one = uuid4()

    # 显式 skill_package_id 优先于绑定集合
    await resolve_skill_for_tool(None, ctx, params={"skill_package_id": str(one)}, bound_skill_ids=[uuid4()])
    assert calls[-1] == (str(one), None)

    # 显式 skill_slug 优先于绑定集合（多绑定下 LLM 的消歧入口）
    await resolve_skill_for_tool(None, ctx, params={"skill_slug": "alpha"}, bound_skill_ids=[one])
    assert calls[-1] == (None, "alpha")

    # 单一绑定：无需显式指定
    await resolve_skill_for_tool(None, ctx, params={}, bound_skill_ids=[one])
    assert calls[-1] == (str(one), None)


@pytest.mark.asyncio
async def test_resolve_rejects_ambiguous_multi_binding(monkeypatch):
    async def _slugs(db, ctx, ids):  # noqa: ANN001, ARG001
        return ["alpha", "beta"]

    monkeypatch.setattr(runtime_mod, "bound_skill_slugs", _slugs)

    with pytest.raises(BadRequestError) as ei:
        await resolve_skill_for_tool(None, _ctx(uuid4()), params={}, bound_skill_ids=[uuid4(), uuid4()])

    # 报错须点名可选 slug，否则 LLM 无从消歧
    assert "alpha" in str(ei.value) and "beta" in str(ei.value)
    assert "skill_slug" in str(ei.value)


@pytest.mark.asyncio
async def test_resolve_requires_binding(monkeypatch):
    with pytest.raises(BadRequestError, match="skill"):
        await resolve_skill_for_tool(None, _ctx(uuid4()), params={}, bound_skill_ids=[])


# --- 4. Prompt 注入 ---------------------------------------------------------


@pytest.mark.asyncio
async def test_prompt_block_injects_each_bound_skill_with_slug(monkeypatch):
    monkeypatch.setattr(agent_context_mod, "is_marked_deleted", lambda _s: False)
    monkeypatch.setattr(agent_context_mod, "read_skill_md", lambda _tid, _s: "正文")

    tid = uuid4()
    ids = [uuid4(), uuid4()]
    skills = {
        str(i): SimpleNamespace(
            id=i,
            tenant_id=tid,
            slug=slug,
            name=name,
            description=None,
            is_active=True,
            tool_names=[],
            prompt_snippet=None,
            config={},
            deleted_at=None,
        )
        for i, slug, name in zip(ids, ["alpha", "beta"], ["甲", "乙"], strict=True)
    }

    class _Db:
        async def get(self, _model, sid):  # noqa: ANN001
            return skills.get(str(sid))

    block = await build_skill_mcp_prompt_block(_Db(), _ctx(tid), {"skill_ids": [str(i) for i in ids]})

    assert "【技能包 · 甲】" in block and "slug: alpha" in block
    assert "【技能包 · 乙】" in block and "slug: beta" in block


@pytest.mark.asyncio
async def test_prompt_block_skips_inactive_bound_skill(monkeypatch):
    monkeypatch.setattr(agent_context_mod, "is_marked_deleted", lambda _s: False)
    monkeypatch.setattr(agent_context_mod, "read_skill_md", lambda _tid, _s: "正文")

    tid = uuid4()
    sid = uuid4()
    skill = SimpleNamespace(
        id=sid,
        tenant_id=tid,
        slug="off",
        name="停用",
        description=None,
        is_active=False,
        tool_names=[],
        prompt_snippet=None,
        config={},
        deleted_at=None,
    )

    class _Db:
        async def get(self, _model, _sid):  # noqa: ANN001
            return skill

    block = await build_skill_mcp_prompt_block(_Db(), _ctx(tid), {"skill_ids": [str(sid)]})
    assert "技能包" not in block
