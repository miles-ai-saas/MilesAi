"""Skill 包管理：供智能体上下文拼装技能说明（见 agents.context）。"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import NotFoundError
from app.core.tenant import TenantContext, assert_tenant_access, tenant_filters
from app.tenant.skills.models import SkillPackage
from app.tenant.skills.schemas.skill import SkillPackageCreate, SkillPackageOut, SkillPackageUpdate
from app.common.schema import PageParams, PageResult
from app.core.soft_delete import append_not_deleted, is_marked_deleted, mark_deleted, not_deleted
from app.core.service import BaseService


class SkillService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)

    async def get_skill(self, skill_id: UUID) -> SkillPackageOut:
        return SkillPackageOut.model_validate(await self._get_or_raise(skill_id))

    async def list_skills(self, params: PageParams) -> PageResult[SkillPackageOut]:
        filters = append_not_deleted(
            tenant_filters(self.ctx, SkillPackage.tenant_id),
            SkillPackage,
        )
        total = await self.db.scalar(
            select(func.count()).select_from(SkillPackage).where(*filters)
        )
        stmt = (
            select(SkillPackage)
            .where(*filters)
            .order_by(SkillPackage.created_at.desc())
            .offset((params.page - 1) * params.size)
            .limit(params.size)
        )
        items = (await self.db.execute(stmt)).scalars().all()
        return PageResult(
            items=[SkillPackageOut.model_validate(i) for i in items],
            total=total or 0,
            page=params.page,
            size=params.size,
        )

    async def create_skill(self, body: SkillPackageCreate) -> SkillPackageOut:
        row = SkillPackage(
            tenant_id=self.ctx.tenant_id,
            name=body.name.strip(),
            description=body.description,
            tool_names=body.tool_names,
            prompt_snippet=body.prompt_snippet,
            config=body.config,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return SkillPackageOut.model_validate(row)

    async def update_skill(self, skill_id: UUID, body: SkillPackageUpdate) -> SkillPackageOut:
        row = await self._get_or_raise(skill_id)
        for k, v in body.model_dump(exclude_unset=True).items():
            setattr(row, k, v)
        await self.db.flush()
        await self.db.refresh(row)
        return SkillPackageOut.model_validate(row)

    async def delete_skill(self, skill_id: UUID) -> None:
        row = await self._get_or_raise(skill_id)
        await mark_deleted(self.db, row)

    async def _get_or_raise(self, skill_id: UUID) -> SkillPackage:
        row = await self.db.get(SkillPackage, skill_id)
        if not row or is_marked_deleted(row):
            raise NotFoundError("技能包不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        return row
