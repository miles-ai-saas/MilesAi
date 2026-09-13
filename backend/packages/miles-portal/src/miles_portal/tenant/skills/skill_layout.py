"""技能包目录布局（references / scripts / assets）与索引构建。

对齐 Agent Skills 约定：SKILL.md 精简注入，references 按需读取，scripts 沙箱执行。
"""

from __future__ import annotations

from pathlib import Path

from miles_portal.tenant.skills.storage import SKILL_MD_FILENAME, skill_package_dir

LAYOUT_VERSION = "1"
REFERENCES_DIR = "references"
SCRIPTS_DIR = "scripts"
ASSETS_DIR = "assets"

REFERENCE_EXTENSIONS = {".md", ".txt", ".json", ".yaml", ".yml", ".csv", ".toml"}
SCRIPT_EXTENSIONS = {".py", ".sh"}

_SUMMARY_MAX = 120
_DEFAULT_READ_MAX = 12_000


def _first_line_summary(text: str) -> str:
    for line in text.splitlines():
        s = line.strip().lstrip("#").strip()
        if s:
            return s[:_SUMMARY_MAX]
    return ""


def _scan_dir(base: Path, subdir: str, extensions: set[str]) -> list[dict]:
    root = base / subdir
    if not root.is_dir():
        return []
    items: list[dict] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.name.startswith("."):
            continue
        if path.suffix.lower() not in extensions and subdir != ASSETS_DIR:
            continue
        rel = path.relative_to(base).as_posix()
        summary = ""
        if path.suffix.lower() in {".md", ".txt"}:
            try:
                summary = _first_line_summary(path.read_text(encoding="utf-8")[:2000])
            except OSError:
                pass
        items.append({"path": rel, "summary": summary})
    return items


def build_layout_index(tenant_id, slug: str) -> dict:
    """扫描磁盘，生成写入 SkillPackage.config['layout'] 的索引。"""
    base = skill_package_dir(tenant_id, slug)
    warnings: list[str] = []
    if not (base / SKILL_MD_FILENAME).is_file():
        warnings.append("缺少 SKILL.md")

    reference_index = _scan_dir(base, REFERENCES_DIR, REFERENCE_EXTENSIONS)
    script_index = _scan_dir(base, SCRIPTS_DIR, SCRIPT_EXTENSIONS)
    asset_index = _scan_dir(base, ASSETS_DIR, REFERENCE_EXTENSIONS | {".png", ".jpg", ".jpeg", ".svg", ".webp"})

    return {
        "layout_version": LAYOUT_VERSION,
        "reference_index": reference_index,
        "script_index": script_index,
        "asset_index": asset_index,
        "warnings": warnings,
    }


def merge_layout_into_config(config: dict | None, layout: dict) -> dict:
    """保留 config 其它键，更新 layout 子树。"""
    out = dict(config or {})
    out["layout"] = {
        "layout_version": layout.get("layout_version", LAYOUT_VERSION),
        "reference_index": layout.get("reference_index") or [],
        "script_index": layout.get("script_index") or [],
        "asset_index": layout.get("asset_index") or [],
        "warnings": layout.get("warnings") or [],
    }
    return out


def _resolve_under_skill_root(base: Path, rel_path: str) -> Path:
    rel = rel_path.strip().lstrip("/")
    if not rel or ".." in rel.split("/"):
        raise ValueError("非法路径")
    target = (base / rel).resolve()
    if not str(target).startswith(str(base.resolve())):
        raise ValueError("非法路径")
    if not target.is_file():
        raise FileNotFoundError(rel)
    return target


def read_skill_resource(
    tenant_id,
    slug: str,
    rel_path: str,
    *,
    max_chars: int = _DEFAULT_READ_MAX,
    allowed_prefixes: tuple[str, ...] = (f"{REFERENCES_DIR}/", f"{ASSETS_DIR}/", ""),
) -> dict:
    """读取技能包内文本资源；空 prefix 允许 SKILL.md。"""
    base = skill_package_dir(tenant_id, slug).resolve()
    rel = rel_path.strip().lstrip("/")
    if rel == SKILL_MD_FILENAME:
        allowed = True
    else:
        allowed = any(rel.startswith(p) for p in allowed_prefixes if p)
    if not allowed:
        raise ValueError(f"路径须位于 references/ 或 assets/ 下: {rel_path}")

    target = _resolve_under_skill_root(base, rel)
    if target.suffix.lower() not in REFERENCE_EXTENSIONS and rel != SKILL_MD_FILENAME:
        raise ValueError("不支持的文件类型")

    text = target.read_text(encoding="utf-8")
    truncated = False
    if len(text) > max_chars:
        text = text[:max_chars]
        truncated = True
    return {"path": rel, "content": text, "truncated": truncated, "size": len(text)}


def read_skill_script_source(tenant_id, slug: str, rel_path: str) -> str:
    """读取 ``scripts/`` 下的脚本源码，仅允许 .py/.sh，越界路径抛 ``ValueError``。"""
    rel = rel_path.strip().lstrip("/")
    if not rel.startswith(f"{SCRIPTS_DIR}/"):
        raise ValueError(f"脚本路径须位于 {SCRIPTS_DIR}/ 下")
    base = skill_package_dir(tenant_id, slug).resolve()
    target = _resolve_under_skill_root(base, rel)
    if target.suffix.lower() not in SCRIPT_EXTENSIONS:
        raise ValueError("暂仅支持 .py / .sh 脚本")
    return target.read_text(encoding="utf-8")


def format_layout_prompt_blocks(layout: dict | None) -> list[str]:
    """生成注入 system prompt 的索引块（非全文）。"""
    if not layout:
        return []
    parts: list[str] = []
    refs = layout.get("reference_index") or []
    if refs:
        lines = []
        for item in refs[:24]:
            p = item.get("path", "")
            s = item.get("summary") or ""
            lines.append(f"- {p}" + (f" — {s}" if s else ""))
        parts.append("【技能参考索引】需要详细说明时用 skill_read_reference 读取，勿臆造：\n" + "\n".join(lines))
    scripts = layout.get("script_index") or []
    if scripts:
        lines = []
        for item in scripts[:16]:
            p = item.get("path", "")
            s = item.get("summary") or ""
            lines.append(f"- {p}" + (f" — {s}" if s else ""))
        parts.append("【技能脚本索引】需要执行时用 skill_run_script，路径相对技能根：\n" + "\n".join(lines))
    return parts


def scaffold_blank_layout(tenant_id, slug: str, *, name: str) -> None:
    """空白技能包：创建 references/、scripts/ 与示例文件。"""
    from miles_portal.tenant.skills.skill_md import build_skill_md
    from miles_portal.tenant.skills.storage import write_file, write_skill_md

    base = skill_package_dir(tenant_id, slug)
    (base / REFERENCES_DIR).mkdir(parents=True, exist_ok=True)
    (base / SCRIPTS_DIR).mkdir(parents=True, exist_ok=True)

    body = """## 使用说明

1. 在正文中保持精简步骤；详细文档放入 `references/`。
2. 可执行逻辑放入 `scripts/`，对话中通过 `skill_run_script` 调用。
3. 需要深入阅读时，使用 `skill_read_reference` 加载 references 下的文件。

## 参考文档

详见 `references/guide.md`。
"""
    write_skill_md(tenant_id, slug, build_skill_md(name, None, body))

    guide = """# 技能参考文档

在此目录放置按需加载的说明（API 手册、边界案例、长示例等）。
对话时 LLM 通过 `skill_read_reference` 读取，不会默认全部注入 Prompt。
"""
    write_file(tenant_id, slug, f"{REFERENCES_DIR}/guide.md", guide)

    example_py = '''"""示例脚本：统计文本词数。由 skill_run_script 在沙箱中执行。"""


def run(params):
    text = str(params.get("text") or "")
    words = [w for w in text.split() if w.strip()]
    return {"word_count": len(words), "char_count": len(text)}
'''
    write_file(tenant_id, slug, f"{SCRIPTS_DIR}/example_validate.py", example_py)
