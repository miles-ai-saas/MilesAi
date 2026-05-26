"""租户全局标签：CRUD、实体绑定、列表筛选。

表结构：
- ``tnt_tags``：租户内 (tenant_id, slug) 唯一
- ``tnt_entity_tag_bindings``：多对多，``entity_type`` + ``entity_id`` + ``tag_id``

由 Agent/Prompt/Skill/Tool/Flow 服务在写入后调用 ``replace_entity_tags``；
删除资源时调用 ``clear_entity_tags``。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError, ConflictError, NotFoundError
from app.core.service import BaseService
from app.core.soft_delete import is_marked_deleted, mark_deleted, not_deleted
from app.core.tenant import TenantContext, assert_tenant_access, tenant_filters
from app.models.tag import EntityTagBinding, TagEntityType, TenantTag
from app.tenant.categories.services.category import slugify
from app.tenant.tags.meta import tags_meta_dict
from app.tenant.tags.schemas.meta import TagMetaOut
from app.tenant.tags.schemas.tag import TagRefOut, TenantTagCreate, TenantTagOut


def parse_entity_type(value: str) -> str:
    """校验并规范化绑定表中的 entity_type 字符串。"""
    raw = value.strip().lower()
    allowed = {e.value for e in TagEntityType}
    if raw not in allowed:
        raise BadRequestError(f"entity_type 须为: {', '.join(sorted(allowed))}")
    return raw


class TagService(BaseService):
    """租户全局标签服务（跨 agent/prompt/skill/tool/flow）。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)

    async def get_meta(self) -> TagMetaOut:
        """返回枚举展示字典（无 DB 查询，文案来自 tenant/*/meta.py）。"""
        return TagMetaOut.model_validate(tags_meta_dict())

    async def list_tags(self) -> list[TenantTagOut]:
        """本租户标签库全量列表。"""
        stmt = (
            select(TenantTag)
            .where(*tenant_filters(self.ctx, TenantTag.tenant_id), not_deleted(TenantTag))
            .order_by(TenantTag.name.asc())
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        return [TenantTagOut.model_validate(r) for r in rows]

    async def create_tag(self, body: TenantTagCreate) -> TenantTagOut:
        """按 name 创建标签；slug 冲突视为同名已存在。"""
        name = body.name.strip()
        slug = slugify(name)
        exists = await self.db.scalar(
            select(TenantTag.id)
            .where(
                TenantTag.tenant_id == self.ctx.tenant_id,
                TenantTag.slug == slug,
                not_deleted(TenantTag),
            )
            .limit(1)
        )
        if exists:
            raise ConflictError(f"标签「{name}」已存在")
        row = TenantTag(tenant_id=self.ctx.tenant_id, name=name, slug=slug)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return TenantTagOut.model_validate(row)

    async def delete_tag(self, tag_id: UUID) -> None:
        """删除标签行并清理全部绑定关系。"""
        row = await self._get_tag_or_raise(tag_id)
        await self.db.execute(
            delete(EntityTagBinding).where(
                EntityTagBinding.tenant_id == self.ctx.tenant_id,
                EntityTagBinding.tag_id == row.id,
            )
        )
        await mark_deleted(self.db, row)

    async def _get_tag_or_raise(self, tag_id: UUID) -> TenantTag:
        row = await self.db.get(TenantTag, tag_id)
        if not row or is_marked_deleted(row):
            raise NotFoundError("标签不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        return row

    async def _resolve_tag_ids(self, tag_ids: list[UUID]) -> list[TenantTag]:
        """校验 tag_ids 均属于当前租户，否则 BadRequest。"""
        if not tag_ids:
            return []
        stmt = select(TenantTag).where(
            TenantTag.id.in_(tag_ids),
            *tenant_filters(self.ctx, TenantTag.tenant_id),
            not_deleted(TenantTag),
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        found = {r.id for r in rows}
        missing = [tid for tid in tag_ids if tid not in found]
        if missing:
            raise BadRequestError("存在无效标签")
        return rows

    async def replace_entity_tags(
        self,
        entity_type: str | TagEntityType,
        entity_id: UUID,
        tag_ids: list[UUID],
    ) -> None:
        """全量替换某资源上的标签绑定（先删后插）。"""
        et = entity_type.value if isinstance(entity_type, TagEntityType) else parse_entity_type(entity_type)
        tags = await self._resolve_tag_ids(tag_ids)
        await self.db.execute(
            delete(EntityTagBinding).where(
                EntityTagBinding.tenant_id == self.ctx.tenant_id,
                EntityTagBinding.entity_type == et,
                EntityTagBinding.entity_id == entity_id,
            )
        )
        for tag in tags:
            self.db.add(
                EntityTagBinding(
                    tenant_id=self.ctx.tenant_id,
                    entity_type=et,
                    entity_id=entity_id,
                    tag_id=tag.id,
                )
            )
        await self.db.flush()

    async def clear_entity_tags(self, entity_type: str | TagEntityType, entity_id: UUID) -> None:
        """资源删除时移除其全部标签绑定。"""
        et = entity_type.value if isinstance(entity_type, TagEntityType) else parse_entity_type(entity_type)
        await self.db.execute(
            delete(EntityTagBinding).where(
                EntityTagBinding.tenant_id == self.ctx.tenant_id,
                EntityTagBinding.entity_type == et,
                EntityTagBinding.entity_id == entity_id,
            )
        )

    async def get_refs_map(
        self,
        entity_type: str | TagEntityType,
        entity_ids: set[UUID],
    ) -> dict[UUID, list[TagRefOut]]:
        """批量加载资源的标签列表，用于列表/详情 Out。"""
        if not entity_ids:
            return {}
        et = entity_type.value if isinstance(entity_type, TagEntityType) else parse_entity_type(entity_type)
        stmt = (
            select(
                EntityTagBinding.entity_id,
                TenantTag.id,
                TenantTag.name,
                TenantTag.slug,
            )
            .join(TenantTag, TenantTag.id == EntityTagBinding.tag_id)
            .where(
                EntityTagBinding.tenant_id == self.ctx.tenant_id,
                EntityTagBinding.entity_type == et,
                EntityTagBinding.entity_id.in_(entity_ids),
                not_deleted(TenantTag),
            )
            .order_by(TenantTag.name.asc())
        )
        rows = (await self.db.execute(stmt)).all()
        out: dict[UUID, list[TagRefOut]] = {}
        for entity_id, tag_id, name, slug in rows:
            out.setdefault(entity_id, []).append(TagRefOut(id=tag_id, name=name, slug=slug))
        return out

    def entity_id_filter(self, entity_type: str | TagEntityType, tag_ids: list[UUID]):
        """返回 IN 子查询：实体至少拥有 tag_ids 中的一个标签；无 tag_ids 时返回 None。"""
        if not tag_ids:
            return None
        et = entity_type.value if isinstance(entity_type, TagEntityType) else parse_entity_type(entity_type)
        return (
            select(EntityTagBinding.entity_id)
            .where(
                EntityTagBinding.tenant_id == self.ctx.tenant_id,
                EntityTagBinding.entity_type == et,
                EntityTagBinding.tag_id.in_(tag_ids),
            )
            .distinct()
        )
