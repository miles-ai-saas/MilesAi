"""技能包文件存储：按租户/slug 目录落盘。

布局：`{skills_data_root}/{tenant_id}/{slug}/SKILL.md` + 附属文件。
导入（import_service）与删除（SkillService.delete_skill）均通过本模块操作磁盘。
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from uuid import UUID

from miles_core.config import get_settings

SKILL_MD_FILENAME = "SKILL.md"
_SLUG_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$")
_MAX_ZIP_BYTES = 100 * 1024 * 1024  # 与 import_zip 校验一致


def skill_slug_from_folder(name: str) -> str:
    """目录名 → slug；导入时以子目录名为准，冲突策略见 overwrite_existing。"""
    raw = name.strip()
    s = re.sub(r"[^a-zA-Z0-9_-]+", "_", raw).strip("_")
    if s and _SLUG_RE.match(s):
        return s[:128]
    digest = re.sub(r"[^a-zA-Z0-9]+", "", raw)[:32]
    return (digest or "skill")[:128]


def skills_data_root() -> Path:
    """解析 SKILLS_DATA_ROOT；相对路径时锚定 backend 目录并确保存在。"""
    settings = get_settings()
    root = Path(settings.skills_data_root)
    if not root.is_absolute():
        backend_dir = Path(__file__).resolve().parents[3]
        root = backend_dir / root
    root.mkdir(parents=True, exist_ok=True)
    return root


def tenant_skills_root(tenant_id: UUID) -> Path:
    """单租户技能根目录。"""
    p = skills_data_root() / str(tenant_id)
    p.mkdir(parents=True, exist_ok=True)
    return p


def skill_package_dir(tenant_id: UUID, slug: str) -> Path:
    """单个技能包目录（无 trailing slash 语义差异）。"""
    return tenant_skills_root(tenant_id) / slug


def ensure_skill_md(path: Path, name: str, description: str | None = None) -> Path:
    """目录已存在但无 SKILL.md 时补写模板（create_skill 遗留路径）。"""
    from miles_portal.tenant.skills.skill_md import build_skill_md

    skill_md = path / SKILL_MD_FILENAME
    if not skill_md.exists():
        skill_md.write_text(build_skill_md(name, description), encoding="utf-8")
    return skill_md


def copy_skill_tree(src_dir: Path, dest_dir: Path) -> None:
    """导入时整目录复制；dest 已存在则先 rmtree 再写入。"""
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    for item in src_dir.iterdir():
        target = dest_dir / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)


def remove_skill_dir(tenant_id: UUID, slug: str) -> None:
    """软删技能包时同步清理磁盘（delete_skill）。"""
    d = skill_package_dir(tenant_id, slug)
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def remove_tenant_skills(tenant_id: UUID) -> None:
    """purge_tenant_data 硬删租户时调用。"""
    d = tenant_skills_root(tenant_id)
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def read_skill_md(tenant_id: UUID, slug: str) -> str:
    """读取 SKILL.md；不存在返回空串（agents.context 注入用）。"""
    p = skill_package_dir(tenant_id, slug) / SKILL_MD_FILENAME
    if not p.is_file():
        return ""
    return p.read_text(encoding="utf-8")


def write_skill_md(tenant_id: UUID, slug: str, content: str) -> None:
    """仅写 SKILL.md（create_blank）。"""
    d = skill_package_dir(tenant_id, slug)
    d.mkdir(parents=True, exist_ok=True)
    (d / SKILL_MD_FILENAME).write_text(content, encoding="utf-8")


def write_file(tenant_id: UUID, slug: str, rel_path: str, content: str) -> None:
    """写相对路径文件；resolve 后须在技能根下，防止路径穿越。"""
    base = skill_package_dir(tenant_id, slug).resolve()
    target = (base / rel_path).resolve()
    if not str(target).startswith(str(base)):
        raise ValueError("非法路径")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def delete_file(tenant_id: UUID, slug: str, rel_path: str) -> None:
    """删除相对路径文件；禁止删除 SKILL.md 与路径穿越。"""
    rel = rel_path.strip().lstrip("/")
    if not rel or rel == SKILL_MD_FILENAME:
        raise ValueError("不可删除 SKILL.md")
    if ".." in rel.split("/"):
        raise ValueError("非法路径")
    base = skill_package_dir(tenant_id, slug).resolve()
    target = (base / rel).resolve()
    if not str(target).startswith(str(base)) or not target.is_file():
        raise FileNotFoundError(rel_path)
    target.unlink()


def read_file(tenant_id: UUID, slug: str, rel_path: str) -> str:
    """读相对路径；越界或不存在抛 FileNotFoundError。"""
    base = skill_package_dir(tenant_id, slug).resolve()
    target = (base / rel_path).resolve()
    if not str(target).startswith(str(base)) or not target.is_file():
        raise FileNotFoundError(rel_path)
    return target.read_text(encoding="utf-8")


def list_file_tree(tenant_id: UUID, slug: str) -> list[dict]:
    """递归列出文件树，供 GET /{id}/files；节点含 name/path/type/children。"""
    root = skill_package_dir(tenant_id, slug)
    if not root.exists():
        return []

    def walk(dir_path: Path, prefix: str = "") -> list[dict]:
        nodes: list[dict] = []
        for child in sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            rel = f"{prefix}/{child.name}" if prefix else child.name
            if child.is_dir():
                nodes.append({"name": child.name, "path": rel, "type": "dir", "children": walk(child, rel)})
            else:
                nodes.append({"name": child.name, "path": rel, "type": "file"})
        return nodes

    return walk(root)


def discover_skill_dirs(scan_root: Path) -> list[Path]:
    """扫描可导入的技能目录。

    - 若 scan_root 根下有 SKILL.md → 视为单个技能（根即包目录）；
    - 否则只认一级子目录且内含 SKILL.md（ZIP 的 skills/、Git 的 skills/ 等）。
    """
    found: list[Path] = []
    if not scan_root.is_dir():
        return found
    skill_md_at_root = scan_root / SKILL_MD_FILENAME
    if skill_md_at_root.is_file():
        return [scan_root]
    for child in sorted(scan_root.iterdir()):
        if not child.is_dir():
            continue
        if (child / SKILL_MD_FILENAME).is_file():
            found.append(child)
    return found


def resolve_import_path(path_str: str) -> Path:
    """本地导入路径：绝对路径原样 resolve；相对路径相对 backend 目录。"""
    p = Path(path_str.strip()).expanduser()
    if not p.is_absolute():
        backend_dir = Path(__file__).resolve().parents[3]
        p = (backend_dir / p).resolve()
    return p
