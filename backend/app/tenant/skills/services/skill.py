"""Skill 包业务：CRUD、磁盘文件读写、空白创建。

批量导入见 import_service。运行时注入见 agents.services.context.build_skill_mcp_prompt_block。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError, ConflictError, NotFoundError
from app.core.tenant import TenantContext, assert_tenant_access, tenant_filters
from app.models.meta.category import CategoryDomain, SysCategory
from app.models.meta.tag import TagEntityType
from app.tenant.categories.services.category import CategoryService
from app.tenant.tags.services.tag import TagService
from app.tenant.skills.models import SkillPackage
from app.tenant.skills.meta import skills_meta_dict
from app.tenant.skills.schemas.meta import SkillMetaOut
from app.tenant.skills.schemas.skill import (
    SkillFileContent,
    SkillFileNode,
    SkillFileWrite,
    SkillPackageCreate,
    SkillPackageCreateBlank,
    SkillPackageOut,
    SkillPackageUpdate,
)
from app.tenant.skills.skill_layout import (
    build_layout_index,
    merge_layout_into_config,
    scaffold_blank_layout,
)
from app.tenant.skills.skill_md import build_skill_md, sync_meta_from_skill_md
from app.tenant.skills.storage import (
    SKILL_MD_FILENAME,
    delete_file,
    ensure_skill_md,
    list_file_tree,
    read_file,
    remove_skill_dir,
    skill_package_dir,
    skill_slug_from_folder,
    write_file,
    write_skill_md,
)
from app.common.schema import PageParams, PageResult
from app.core.soft_delete import append_not_deleted, is_marked_deleted, mark_deleted, not_deleted
from app.core.service import BaseService


def _slug_from_name(name: str) -> str:
    """手动创建时由展示名推导 slug（与导入目录名规则一致）。"""
    return skill_slug_from_folder(name)


class SkillService(BaseService):
    """租户技能包服务；依赖 CategoryService 校验 category_id 归属 skill 域。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self._cat = CategoryService(db, ctx)

    async def _refresh_layout(self, row: SkillPackage) -> None:
        layout = build_layout_index(self.ctx.tenant_id, row.slug)
        row.config = merge_layout_into_config(row.config, layout)
        await self.db.flush()

    async def get_meta(self) -> SkillMetaOut:
        """返回枚举展示字典（无 DB 查询，文案来自 tenant/*/meta.py）。"""
        return SkillMetaOut.model_validate(skills_meta_dict())

    async def get_skill(self, skill_id: UUID) -> SkillPackageOut:
        """按 ID 取技能包详情（含 category_name 与标签）。"""
        return await self._to_out(await self._get_or_raise(skill_id))

    async def list_skills(
        self,
        params: PageParams,
        *,
        category_id: UUID | None = None,
        tag_ids: list[UUID] | None = None,
    ) -> PageResult[SkillPackageOut]:
        """分页列表，按 updated_at 降序；category_id 来自工作台 Tab 筛选。"""
        filters = append_not_deleted(
            tenant_filters(self.ctx, SkillPackage.tenant_id),
            SkillPackage,
        )
        if category_id:
            filters.append(SkillPackage.category_id == category_id)
        tag_subq = TagService(self.db, self.ctx).entity_id_filter(TagEntityType.SKILL, tag_ids or [])
        if tag_subq is not None:
            filters.append(SkillPackage.id.in_(tag_subq))
        total = await self.db.scalar(select(func.count()).select_from(SkillPackage).where(*filters))
        stmt = select(SkillPackage).where(*filters).order_by(SkillPackage.updated_at.desc()).offset((params.page - 1) * params.size).limit(params.size)
        items = (await self.db.execute(stmt)).scalars().all()
        tags_map = await TagService(self.db, self.ctx).get_refs_map(TagEntityType.SKILL, {i.id for i in items})
        outs = [await self._to_out(i, tags_map.get(i.id, [])) for i in items]
        return PageResult(items=outs, total=total or 0, page=params.page, size=params.size)

    async def create_skill(self, body: SkillPackageCreate) -> SkillPackageOut:
        """遗留 API：建 ORM 行 + 目录；若带 prompt_snippet 则写入 SKILL.md 正文区。"""
        slug = _slug_from_name(body.name)
        await self._ensure_slug_free(slug)
        if body.category_id:
            await self._cat.validate_category_for_domain(body.category_id, CategoryDomain.SKILL)
        row = SkillPackage(
            tenant_id=self.ctx.tenant_id,
            category_id=body.category_id,
            slug=slug,
            name=body.name.strip(),
            description=body.description,
            source_type="manual",
            storage_path=slug,
            tool_names=body.tool_names,
            prompt_snippet=body.prompt_snippet,
            config=body.config,
        )
        self.db.add(row)
        await self.db.flush()
        ensure_skill_md(skill_package_dir(self.ctx.tenant_id, slug), row.name, row.description)
        if body.prompt_snippet:
            write_skill_md(
                self.ctx.tenant_id,
                slug,
                build_skill_md(row.name, row.description, body.prompt_snippet),
            )
        await self._refresh_layout(row)
        await self.db.refresh(row)
        if body.tag_ids:
            await TagService(self.db, self.ctx).replace_entity_tags(TagEntityType.SKILL, row.id, body.tag_ids)
        return await self._to_out(row)

    async def create_blank(self, body: SkillPackageCreateBlank) -> SkillPackageOut:
        """工作台主路径：仅元数据 + 模板 SKILL.md，前端跳转 /workbench/skills/[id] 编辑。"""
        await self._cat.validate_category_for_domain(body.category_id, CategoryDomain.SKILL)
        slug = _slug_from_name(body.name)
        await self._ensure_slug_free(slug)
        row = SkillPackage(
            tenant_id=self.ctx.tenant_id,
            category_id=body.category_id,
            slug=slug,
            name=body.name.strip(),
            description=body.description,
            source_type="manual",
            storage_path=slug,
        )
        self.db.add(row)
        await self.db.flush()
        scaffold_blank_layout(self.ctx.tenant_id, slug, name=row.name.strip())
        name, desc = sync_meta_from_skill_md(read_file(self.ctx.tenant_id, slug, SKILL_MD_FILENAME))
        if name:
            row.name = name[:128]
        if desc is not None:
            row.description = desc or None
        await self._refresh_layout(row)
        await self.db.refresh(row)
        if body.tag_ids:
            await TagService(self.db, self.ctx).replace_entity_tags(TagEntityType.SKILL, row.id, body.tag_ids)
        return await self._to_out(row)

    async def update_skill(self, skill_id: UUID, body: SkillPackageUpdate) -> SkillPackageOut:
        """只改 DB 字段，不自动改磁盘（名称/描述以编辑器保存 SKILL.md 为准）。"""
        row = await self._get_or_raise(skill_id)
        data = body.model_dump(exclude_unset=True)
        tag_ids = data.pop("tag_ids", None)
        if "category_id" in data and data["category_id"]:
            await self._cat.validate_category_for_domain(data["category_id"], CategoryDomain.SKILL)
        for k, v in data.items():
            setattr(row, k, v)
        await self.db.flush()
        if tag_ids is not None:
            await TagService(self.db, self.ctx).replace_entity_tags(TagEntityType.SKILL, row.id, tag_ids)
        await self.db.refresh(row)
        return await self._to_out(row)

    async def delete_skill(self, skill_id: UUID) -> None:
        """软删 + 删除 tenant/slug 目录（不可恢复磁盘内容）。"""
        row = await self._get_or_raise(skill_id)
        await TagService(self.db, self.ctx).clear_entity_tags(TagEntityType.SKILL, row.id)
        remove_skill_dir(self.ctx.tenant_id, row.slug)
        await mark_deleted(self.db, row)

    async def list_files(self, skill_id: UUID) -> list[SkillFileNode]:
        """返回技能包磁盘文件树。"""
        row = await self._get_or_raise(skill_id)
        tree = list_file_tree(self.ctx.tenant_id, row.slug)
        return [SkillFileNode.model_validate(n) for n in tree]

    async def read_file_content(self, skill_id: UUID, path: str) -> SkillFileContent:
        """读取技能包内文件；文件不存在抛 ``NotFoundError``。"""
        row = await self._get_or_raise(skill_id)
        rel = path.strip().lstrip("/")
        try:
            content = read_file(self.ctx.tenant_id, row.slug, rel)
        except FileNotFoundError as exc:
            raise NotFoundError("文件不存在") from exc
        return SkillFileContent(path=rel, content=content)

    async def write_file_content(self, skill_id: UUID, body: SkillFileWrite) -> SkillFileContent:
        """写盘后若为 SKILL.md，同步 name/description 并将全文记入 prompt_snippet 便于回退检索。"""
        row = await self._get_or_raise(skill_id)
        rel = body.path.strip().lstrip("/")
        if ".." in rel.split("/"):
            raise BadRequestError("非法路径")
        write_file(self.ctx.tenant_id, row.slug, rel, body.content)
        if rel == SKILL_MD_FILENAME or rel.endswith(f"/{SKILL_MD_FILENAME}"):
            name, desc = sync_meta_from_skill_md(body.content)
            if name:
                row.name = name[:128]
            if desc is not None:
                row.description = desc or None
            row.prompt_snippet = body.content
            await self.db.flush()
        await self._refresh_layout(row)
        return SkillFileContent(path=rel, content=body.content)

    async def reindex(self, skill_id: UUID) -> SkillPackageOut:
        """扫描磁盘刷新 config.layout（手动 reindex 或磁盘外部变更后）。"""
        row = await self._get_or_raise(skill_id)
        await self._refresh_layout(row)
        return await self._to_out(row)

    async def delete_file_content(self, skill_id: UUID, path: str) -> None:
        """删除技能包内文件（SKILL.md 不可删），随后刷新 layout 索引。"""
        row = await self._get_or_raise(skill_id)
        rel = path.strip().lstrip("/")
        if not rel or rel == SKILL_MD_FILENAME:
            raise BadRequestError("不可删除 SKILL.md")
        if ".." in rel.split("/"):
            raise BadRequestError("非法路径")
        try:
            delete_file(self.ctx.tenant_id, row.slug, rel)
        except FileNotFoundError as exc:
            raise NotFoundError("文件不存在") from exc
        except ValueError as exc:
            raise BadRequestError(str(exc)) from exc
        await self._refresh_layout(row)

    async def _ensure_slug_free(self, slug: str, *, exclude_id: UUID | None = None) -> None:
        """租户内 slug 唯一（含未软删记录）。"""
        filters = [
            SkillPackage.tenant_id == self.ctx.tenant_id,
            SkillPackage.slug == slug,
            not_deleted(SkillPackage),
        ]
        if exclude_id:
            filters.append(SkillPackage.id != exclude_id)
        exists = await self.db.scalar(select(SkillPackage.id).where(*filters).limit(1))
        if exists:
            raise ConflictError(f"技能标识「{slug}」已存在")

    async def _get_or_raise(self, skill_id: UUID) -> SkillPackage:
        row = await self.db.get(SkillPackage, skill_id)
        if not row or is_marked_deleted(row):
            raise NotFoundError("技能包不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        return row

    async def _to_out(self, row: SkillPackage, tags=None) -> SkillPackageOut:
        """附加 category_name、tags。"""
        cat_name: str | None = None
        if row.category_id:
            cat = await self.db.get(SysCategory, row.category_id)
            if cat and not is_marked_deleted(cat):
                cat_name = cat.name
        if tags is None:
            tags_map = await TagService(self.db, self.ctx).get_refs_map(TagEntityType.SKILL, {row.id})
            tags = tags_map.get(row.id, [])
        data = SkillPackageOut.model_validate(row)
        return data.model_copy(update={"category_name": cat_name, "tags": tags or []})
