"""SKILL.md frontmatter 解析与元数据同步（skill_md 模块）。"""

from app.tenant.skills.skill_md import build_skill_md, parse_skill_md, sync_meta_from_skill_md


def test_parse_skill_md_frontmatter():
    content = """---
name: doGetCurrentTime
description: 获取当前时间
---
正文说明
"""
    meta, body = parse_skill_md(content)
    assert meta["name"] == "doGetCurrentTime"
    assert meta["description"] == "获取当前时间"
    assert body == "正文说明"


def test_build_and_sync():
    md = build_skill_md("测试", "描述")
    name, desc = sync_meta_from_skill_md(md)
    assert name == "测试"
    assert desc == "描述"
