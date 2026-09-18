"""技能包批量导入：本地目录、ZIP、Git 仓库。

流程：校验分类 → 扫描 SKILL.md 目录 → copy_skill_tree → 插入/更新 ORM。
同名 slug 由 overwrite_existing 决定覆盖或跳过（不计入 errors）。

**阻塞调用一律离线**：``git clone`` 是外部进程（地址由用户提供，超时上限 300s），
写包与解压（上传上限 100MB、解压后上限 500MB）均经 ``asyncio.to_thread`` —— 否则
单个挂起的远端或大包会阻塞整个事件循环
（见 ``tests/test_no_blocking_calls_in_async.py``）。

**ZIP 归档规模受限**：上传上限只约束压缩后大小，而文本技能包压缩比可达数十倍，
故 ``_validate_zip_limits`` 另按中央目录的声明值校验解压后总体积与条目数，且**在
解压前**执行（超限归档不落地任何文件）。损坏归档的 ``BadZipFile`` 转成 400 ——
它不是 ``AppError``，不转换会以 500 返回。路径穿越与符号链接成员由 ``zipfile``
自行净化，无需额外守卫。

**Git 地址仅允许 http(s)**：经 ``validate_outbound_url`` 阻断 ``file://`` 等 scheme
（``git clone`` 会识别它们，构成本地文件读取面）。内网 / link-local 拦截由
``outbound_allow_private_hosts`` 控制且**默认为 True**，即默认放行，属运维显式收紧后才
生效的深度防御。
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.exceptions import BadRequestError
from miles_core.models.meta.category import CategoryDomain
from miles_core.soft_delete import not_deleted
from miles_core.tenant import TenantContext
from miles_core.url_security import validate_outbound_url
from miles_portal.tenant.categories.services.category import CategoryService
from miles_portal.tenant.skills.models import SkillPackage
from miles_portal.tenant.skills.schemas.skill import SkillImportResult
from miles_portal.tenant.skills.skill_layout import build_layout_index, merge_layout_into_config
from miles_portal.tenant.skills.skill_md import parse_skill_md
from miles_portal.tenant.skills.storage import (
    SKILL_MD_FILENAME,
    copy_skill_tree,
    discover_skill_dirs,
    resolve_import_path,
    skill_package_dir,
    skill_slug_from_folder,
)

#: ZIP 上传体积上限（压缩后）。
_MAX_ZIP_BYTES = 100 * 1024 * 1024

#: ZIP 解压后**总体积**上限。上传上限只约束压缩后大小，而文本类技能包的压缩比可达
#: 数十倍 —— 数百 KB 的包可膨胀到数十 GB 写满磁盘。取上传上限的 5 倍，既覆盖正常
#: 文本压缩比，又给磁盘占用一个确定上界。
_MAX_ZIP_UNCOMPRESSED_BYTES = 5 * _MAX_ZIP_BYTES

#: ZIP 条目数上限（防 inode 耗尽）。技能包为文本文件，1 万条已远超实际需要。
_MAX_ZIP_ENTRIES = 10_000


def _validate_zip_limits(zf: zipfile.ZipFile) -> None:
    """按中央目录的声明值校验归档规模；超限抛 ``BadRequestError``。

    可以只信声明值：``zipfile`` 按声明的 ``file_size`` 截断读取，实际数据与之不符时
    抛 ``BadZipFile``（CRC 校验），故谎报尺寸者会被拒绝而非绕过。校验在解压**之前**
    执行，超限归档不会落地任何文件。
    """
    infos = zf.infolist()
    if len(infos) > _MAX_ZIP_ENTRIES:
        raise BadRequestError(f"压缩包内文件数超限（{len(infos)} > {_MAX_ZIP_ENTRIES}）")
    total = sum(info.file_size for info in infos)
    if total > _MAX_ZIP_UNCOMPRESSED_BYTES:
        limit_mb = _MAX_ZIP_UNCOMPRESSED_BYTES // (1024 * 1024)
        raise BadRequestError(f"压缩包解压后体积超限（{total // (1024 * 1024)}MB > {limit_mb}MB）")


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
            await asyncio.to_thread(zip_path.write_bytes, file_bytes)
            try:
                with zipfile.ZipFile(zip_path, "r") as zf:
                    _validate_zip_limits(zf)
                    await asyncio.to_thread(zf.extractall, tmp / "extracted")
            except zipfile.BadZipFile as exc:
                # BadZipFile 不是 AppError，不转换会以 500 返回（且丢失原因）
                raise BadRequestError("压缩包不是有效的 zip 或已损坏") from exc
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
        """子进程 git clone --depth 1；需镜像内安装 git 且能访问远端。

        地址仅允许 ``http(s)``（经 ``validate_outbound_url``），阻断 ``file://`` /
        ``ssh://`` / ``git://`` 等 scheme 与内网、link-local（云元数据）地址 ——
        ``git clone`` 会真正发起出站连接并识别这些 scheme。注意该函数不解析域名 DNS，
        故「域名解析到内网」不在拦截范围内（与 HTTP 工具同一限制）。
        """
        await self._cat.validate_category_for_domain(category_id, CategoryDomain.SKILL)
        url = repo_url.strip()
        if not url:
            raise BadRequestError("仓库地址不能为空")
        validate_outbound_url(url)
        tmp = Path(tempfile.mkdtemp(prefix="skill_git_"))
        try:
            proc = await asyncio.to_thread(
                subprocess.run,
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
