"""技能包运行时工具与 Prompt 注入集成测试。"""

from uuid import uuid4

import pytest

from miles_core.tenant import TenantContext
from miles_integrations.langchain.toolkit import catalog as lc_tools
from miles_portal.tenant.agents.services.context import build_skill_mcp_prompt_block
from miles_portal.tenant.skills.skill_layout import build_layout_index, merge_layout_into_config
from miles_portal.tenant.skills.storage import SKILL_MD_FILENAME
from miles_portal.tenant.tools.invoke import invoke_builtin


def _test_ctx(tenant_id):
    return TenantContext(
        user_id=uuid4(),
        tenant_id=tenant_id,
        username="tester",
        is_superuser=True,
        permissions=frozenset(),
    )


@pytest.fixture
def skill_tree(tmp_path, monkeypatch):
    tid = uuid4()
    slug = "demo-skill"
    skill_id = uuid4()

    def _dir(tid_arg, s):
        return tmp_path / str(tid_arg) / s

    monkeypatch.setattr("miles_portal.tenant.skills.skill_layout.skill_package_dir", _dir)
    monkeypatch.setattr("miles_portal.tenant.skills.storage.skill_package_dir", _dir)

    base = _dir(tid, slug)
    base.mkdir(parents=True)
    (base / SKILL_MD_FILENAME).write_text("---\nname: Demo\n---\n正文\n", encoding="utf-8")
    (base / "references").mkdir()
    (base / "references" / "guide.md").write_text("# Guide\n细节", encoding="utf-8")

    layout = build_layout_index(tid, slug)
    config = merge_layout_into_config({}, layout)

    skill_obj = type(
        "_Skill",
        (),
        {
            "id": skill_id,
            "tenant_id": tid,
            "slug": slug,
            "name": "Demo",
            "description": None,
            "is_active": True,
            "tool_names": [],
            "prompt_snippet": None,
            "config": config,
            "deleted_at": None,
        },
    )()

    monkeypatch.setattr("miles_portal.tenant.agents.services.context.is_marked_deleted", lambda _s: False)
    monkeypatch.setattr(
        "miles_portal.tenant.agents.services.context.read_skill_md",
        lambda _tid, _s: (base / SKILL_MD_FILENAME).read_text(encoding="utf-8"),
    )

    return {
        "tenant_id": tid,
        "skill_id": skill_id,
        "slug": slug,
        "skill": skill_obj,
    }


def test_build_platform_tools_skill_bound():
    """绑定 ``skill_package_id`` 时装配工具应含 ``skill_*``；否则不含。"""
    without = lc_tools.build_platform_tools({}, [])
    with_skill = lc_tools.build_platform_tools({"skill_package_id": str(uuid4())}, [])

    names_without = {t.name for t in without}
    names_with = {t.name for t in with_skill}

    assert "skill_read_reference" not in names_without
    assert "skill_run_script" not in names_without
    assert "skill_read_reference" in names_with
    assert "skill_run_script" in names_with


@pytest.mark.asyncio
async def test_build_skill_mcp_prompt_includes_layout_index(skill_tree):
    data = skill_tree

    class _Db:
        async def get(self, _model, _id):
            return data["skill"]

    block = await build_skill_mcp_prompt_block(
        _Db(),
        _test_ctx(data["tenant_id"]),
        {"skill_package_id": str(data["skill_id"])},
    )
    assert "【技能包 · Demo】" in block
    assert "【技能参考索引】" in block
    assert "references/guide.md" in block
    assert "skill_read_reference" in block


@pytest.mark.asyncio
async def test_invoke_skill_read_reference(skill_tree, monkeypatch):
    data = skill_tree
    ctx = _test_ctx(data["tenant_id"])

    async def _resolve(*_args, **_kwargs):
        return data["skill"]

    monkeypatch.setattr("miles_portal.tenant.skills.runtime.resolve_bound_skill", _resolve)

    out = await invoke_builtin(
        "skill_read_reference",
        {"path": "references/guide.md"},
        db=None,
        ctx=ctx,
        bound_skill_ids=[data["skill_id"]],
    )
    assert "Guide" in out["content"]
