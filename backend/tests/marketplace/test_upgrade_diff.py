"""应用升级 diff 工具测试。"""

from uuid import uuid4

from app.tenant.marketplace.util.upgrade_diff import (
    build_upgrade_preview,
    diff_agent,
    diff_flow,
    diff_knowledge_base,
)


def test_diff_knowledge_base_detects_name_change():
    diff = diff_knowledge_base(
        resource_id=uuid4(),
        current_name="旧名称",
        current_description="旧描述",
        target={"name": "新名称", "description": "旧描述"},
    )
    assert diff.has_changes is True
    name_change = next(c for c in diff.changes if c.field == "name")
    assert name_change.changed is True
    assert name_change.before == "旧名称"
    assert name_change.after == "新名称"


def test_diff_flow_graph_structure_change():
    current_graph = {"nodes": [{"id": "a"}], "edges": []}
    target_graph = {"nodes": [{"id": "a"}, {"id": "b"}], "edges": [{"from": "a", "to": "b"}]}
    diff = diff_flow(
        resource_id=uuid4(),
        current_name="流程",
        current_description=None,
        current_graph=current_graph,
        target={"name": "流程", "graph_json": target_graph},
    )
    assert diff.has_changes is True
    structure = next(c for c in diff.changes if c.field == "graph_structure")
    assert structure.changed is True


def test_diff_agent_truncates_long_prompt():
    long_prompt = "x" * 500
    diff = diff_agent(
        resource_id=uuid4(),
        current_name="Agent",
        current_description=None,
        current_system_prompt="short",
        target={"name": "Agent", "system_prompt": long_prompt},
    )
    prompt_change = next(c for c in diff.changes if c.field == "system_prompt")
    assert prompt_change.changed is True
    assert prompt_change.after is not None
    assert len(prompt_change.after) <= 400
    assert prompt_change.after.endswith("…")


def test_build_upgrade_preview_same_version():
    preview = build_upgrade_preview(
        app_id=uuid4(),
        app_name="Demo",
        installed_version="1.0.0",
        target_version="1.0.0",
        resources=[],
    )
    assert preview.can_upgrade is False
    assert preview.message == "已是最新版本"


def test_build_upgrade_preview_version_only():
    diff = diff_knowledge_base(
        resource_id=uuid4(),
        current_name="KB",
        current_description="desc",
        target={"name": "KB", "description": "desc"},
    )
    preview = build_upgrade_preview(
        app_id=uuid4(),
        app_name="Demo",
        installed_version="1.0.0",
        target_version="1.1.0",
        resources=[diff],
    )
    assert preview.can_upgrade is True
    assert preview.has_changes is False
    assert "版本号有更新" in (preview.message or "")
