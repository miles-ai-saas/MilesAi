"""技能包目录布局：索引构建、Prompt 块、资源读取。"""

from uuid import uuid4

import pytest

from app.tenant.skills.skill_layout import (
    build_layout_index,
    format_layout_prompt_blocks,
    merge_layout_into_config,
    read_skill_resource,
    read_skill_script_source,
)
from app.tenant.skills.storage import SKILL_MD_FILENAME


@pytest.fixture
def skill_tree(tmp_path, monkeypatch):
    tenant_id = uuid4()
    slug = "demo-skill"

    def _dir(tid, s):
        return tmp_path / str(tid) / s

    monkeypatch.setattr("app.tenant.skills.skill_layout.skill_package_dir", _dir)
    monkeypatch.setattr("app.tenant.skills.storage.skill_package_dir", _dir)

    base = _dir(tenant_id, slug)
    base.mkdir(parents=True)
    (base / SKILL_MD_FILENAME).write_text("---\nname: Demo\n---\n", encoding="utf-8")
    (base / "references").mkdir()
    (base / "references" / "guide.md").write_text("# Guide\n详细说明", encoding="utf-8")
    (base / "scripts").mkdir()
    (base / "scripts" / "run.py").write_text("def run(p):\n    return p\n", encoding="utf-8")
    return tenant_id, slug


def test_build_layout_index(skill_tree):
    tenant_id, slug = skill_tree
    layout = build_layout_index(tenant_id, slug)
    assert layout["reference_index"][0]["path"] == "references/guide.md"
    assert layout["script_index"][0]["path"] == "scripts/run.py"
    assert layout["warnings"] == []


def test_merge_and_prompt_blocks(skill_tree):
    tenant_id, slug = skill_tree
    layout = build_layout_index(tenant_id, slug)
    merged = merge_layout_into_config({"foo": 1}, layout)
    assert merged["foo"] == 1
    assert merged["layout"]["reference_index"]

    blocks = format_layout_prompt_blocks(merged["layout"])
    assert len(blocks) == 2
    assert "skill_read_reference" in blocks[0]
    assert "references/guide.md" in blocks[0]
    assert "skill_run_script" in blocks[1]


def test_read_skill_resource_and_script(skill_tree):
    tenant_id, slug = skill_tree
    doc = read_skill_resource(tenant_id, slug, "references/guide.md")
    assert "Guide" in doc["content"]
    source = read_skill_script_source(tenant_id, slug, "scripts/run.py")
    assert "def run" in source


def test_read_skill_resource_rejects_traversal(skill_tree):
    tenant_id, slug = skill_tree
    with pytest.raises(ValueError):
        read_skill_resource(tenant_id, slug, "references/../../etc/passwd")
