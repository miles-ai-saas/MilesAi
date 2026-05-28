"""技能包批量导入：本地目录、ZIP、Git 仓库。

流程：校验分类 → 扫描 SKILL.md 目录 → copy_skill_tree → 插入/更新 ORM。
同名 slug 由 overwrite_existing 决定覆盖或跳过（不计入 errors）。
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError
from app.core.tenant import TenantContext
from app.models.category import CategoryDomain
from app.tenant.categories.services.category import CategoryService
from app.tenant.skills.models import SkillPackage
from app.tenant.skills.schemas.skill import SkillImportResult
from app.tenant.skills.skill_layout import build_layout_index, merge_layout_into_config
from app.tenant.skills.skill_md import parse_skill_md
from app.tenant.skills.storage import (
    SKILL_MD_FILENAME,
    _MAX_ZIP_BYTES,
    copy_skill_tree,
    discover_skill_dirs,
    resolve_import_path,
    skill_package_dir,
    skill_slug_from_folder,
)
from app.core.soft_delete import not_deleted


class SkillImportService:
    """无独立事务边界：由 get_db 在视图层统一 commit。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        self.db = db
        self.ctx = ctx
        self._cat = CategoryService(db, ctx)

    async def import_local(
        self,
        category_id: UUID,
        local_path: str,
        *,
        overwrite_existing: bool,
    ) -> SkillImportResult:
        """扫描服务端 local_path（见 storage.resolve_import_path）。"""
        await self._cat.validate_category_for_domain(category_id, CategoryDomain.SKILL)
        root = resolve_import_path(local_path)
        if not root.is_dir():
            raise BadRequestError(f"路径不存在或不可读: {local_path}")
        return await self._import_dirs(
            discover_skill_dirs(root),
            category_id,
            source_type="local",
            overwrite_existing=overwrite_existing,
        )

    async def import_zip(
        self,
        category_id: UUID,
        file_bytes: bytes,
        filename: str,
        *,
        overwrite_existing: bool,
    ) -> SkillImportResult:
        """解压到临时目录，要求存在 extracted/skills/ 再 discover。"""
        await self._cat.validate_category_for_domain(category_id, CategoryDomain.SKILL)
        if len(file_bytes) > _MAX_ZIP_BYTES:
            raise BadRequestError("压缩包不能超过 100MB")
        if not filename.lower().endswith(".zip"):
            raise BadRequestError("仅支持 .zip 文件")
        tmp = Path(tempfile.mkdtemp(prefix="skill_zip_"))
        try:
            zip_path = tmp / "upload.zip"
            zip_path.write_bytes(file_bytes)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(tmp / "extracted")
            extracted = tmp / "extracted"
            skills_root = extracted / "skills"
            if not skills_root.is_dir():
                raise BadRequestError("压缩包解压后须包含 skills/ 目录")
            return await self._import_dirs(
                discover_skill_dirs(skills_root),
                category_id,
                source_type="zip",
                overwrite_existing=overwrite_existing,
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    async def import_git(
        self,
        category_id: UUID,
        repo_url: str,
        *,
        overwrite_existing: bool,
    ) -> SkillImportResult:
        """子进程 git clone --depth 1；需镜像内安装 git 且能访问远端。"""
        await self._cat.validate_category_for_domain(category_id, CategoryDomain.SKILL)
        url = repo_url.strip()
        if not url:
            raise BadRequestError("仓库地址不能为空")
        tmp = Path(tempfile.mkdtemp(prefix="skill_git_"))
        try:
            proc = subprocess.run(
                ["git", "clone", "--depth", "1", url, str(tmp / "repo")],
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
            if proc.returncode != 0:
                err = (proc.stderr or proc.stdout or "clone failed").strip()
                raise BadRequestError(f"Git 克隆失败: {err[:500]}")
            repo = tmp / "repo"
            scan = repo / "skills"
            if scan.is_dir():
                dirs = discover_skill_dirs(scan)
            else:
                dirs = discover_skill_dirs(repo)
            return await self._import_dirs(
                dirs,
                category_id,
                source_type="git",
                overwrite_existing=overwrite_existing,
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    async def _import_dirs(
        self,
        skill_dirs: list[Path],
        category_id: UUID,
        *,
        source_type: str,
        overwrite_existing: bool,
    ) -> SkillImportResult:
        """逐目录导入；单目录异常只记入 errors，不中断其它目录。"""
        result = SkillImportResult()
        if not skill_dirs:
            result.errors.append("未发现包含 SKILL.md 的技能目录")
            return result

        for src in skill_dirs:
            skill_md = src / SKILL_MD_FILENAME
            if not skill_md.is_file():
                result.errors.append(f"{src.name}: 缺少 SKILL.md")
                continue
            try:
                content = skill_md.read_text(encoding="utf-8")
                meta, _ = parse_skill_md(content)
                slug = skill_slug_from_folder(src.name)
                display_name = str(meta.get("name") or src.name).strip()[:128]
                desc = str(meta.get("description") or "").strip() or None

                existing = await self._get_by_slug(slug)
                if existing and not overwrite_existing:
                    result.skipped += 1
                    continue

                dest = skill_package_dir(self.ctx.tenant_id, slug)
                copy_skill_tree(src, dest)

                row: SkillPackage
                if existing:
                    existing.name = display_name
                    existing.description = desc
                    existing.category_id = category_id
                    existing.source_type = source_type
                    existing.storage_path = slug
                    row = existing
                    await self.db.flush()
                    result.imported += 1
                else:
                    row = SkillPackage(
                        tenant_id=self.ctx.tenant_id,
                        category_id=category_id,
                        slug=slug,
                        name=display_name,
                        description=desc,
                        source_type=source_type,
                        storage_path=slug,
                    )
                    self.db.add(row)
                    await self.db.flush()
                    result.imported += 1

                layout = build_layout_index(self.ctx.tenant_id, slug)
                row.config = merge_layout_into_config(row.config, layout)
                await self.db.flush()
            except Exception as exc:
                result.errors.append(f"{src.name}: {exc}")
        return result

    async def _get_by_slug(self, slug: str) -> SkillPackage | None:
        return await self.db.scalar(
            select(SkillPackage)
            .where(
                SkillPackage.tenant_id == self.ctx.tenant_id,
                SkillPackage.slug == slug,
                not_deleted(SkillPackage),
            )
            .limit(1)
        )
