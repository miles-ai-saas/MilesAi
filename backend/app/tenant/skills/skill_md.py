"""SKILL.md 解析与生成（YAML frontmatter + Markdown 正文）。

不依赖 PyYAML：frontmatter 按行解析 `key: value`。保存 SKILL.md 时由 SkillService 调用 sync_meta_from_skill_md 回写 DB。
"""

from __future__ import annotations

import re
from typing import Any

# 文件须以 --- 开头的前置元数据块结束于第二个 ---
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def parse_skill_md(content: str) -> tuple[dict[str, Any], str]:
    """解析 SKILL.md，返回 (frontmatter 字典, Markdown 正文)。

    无 frontmatter 时 meta 为空 dict，全文视为正文。
    """
    text = content or ""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text.strip()
    raw_fm = m.group(1)
    body = text[m.end() :].strip()
    meta: dict[str, Any] = {}
    for line in raw_fm.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip().strip("'\"")
        meta[key] = val
    return meta, body


def build_skill_md(name: str, description: str | None = None, body: str = "") -> str:
    """生成标准 SKILL.md（create_blank / ensure_skill_md 使用）。"""
    desc = (description or "").replace("\n", " ")
    lines = ["---", f"name: {name}", f"description: {desc}", "---", ""]
    if body.strip():
        lines.append(body.strip())
        lines.append("")
    return "\n".join(lines)


def sync_meta_from_skill_md(content: str) -> tuple[str | None, str | None]:
    """从 SKILL.md 提取 name、description，供写文件后同步 ORM 字段。"""
    meta, _ = parse_skill_md(content)
    name = meta.get("name")
    desc = meta.get("description")
    return (
        str(name).strip() if name else None,
        str(desc).strip() if desc else None,
    )
