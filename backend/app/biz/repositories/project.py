"""项目仓储。"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import BaseRepository
from app.core.soft_delete import not_deleted
from app.models.biz import BizProject, BizProjectMember, BizWorkPackage


class ProjectRepository(BaseRepository[BizProject]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, BizProject)

    async def get_work_packages(self, tenant_id: UUID, project_id: UUID) -> list[BizWorkPackage]:
        stmt = (
            select(BizWorkPackage)
            .where(
                BizWorkPackage.tenant_id == tenant_id,
                BizWorkPackage.project_id == project_id,
                not_deleted(BizWorkPackage),
            )
            .order_by(BizWorkPackage.stage_index.asc(), BizWorkPackage.name.asc())
        )
        return (await self.db.execute(stmt)).scalars().all()

    async def list_work_packages_filtered(
        self,
        tenant_id: UUID,
        *,
        project_id: UUID | None = None,
        service_line: str | None = None,
        status: str | None = None,
        limit: int = 200,
    ) -> list:
        """返回 (工作包, 项目名, 客户名) 行列表。"""
        from app.models.biz import BizClient

        stmt = (
            select(BizWorkPackage, BizProject.name.label("project_name"), BizClient.name.label("client_name"))
            .join(BizProject, BizProject.id == BizWorkPackage.project_id)
            .join(BizClient, BizClient.id == BizProject.client_id, isouter=True)
            .where(
                BizWorkPackage.tenant_id == tenant_id,
                not_deleted(BizWorkPackage),
                not_deleted(BizProject),
            )
            .order_by(BizWorkPackage.updated_at.desc(), BizWorkPackage.name.asc())
            .limit(limit)
        )
        if project_id:
            stmt = stmt.where(BizWorkPackage.project_id == project_id)
        if service_line:
            stmt = stmt.where(BizWorkPackage.service_line == service_line)
        if status:
            stmt = stmt.where(BizWorkPackage.status == status)
        return (await self.db.execute(stmt)).all()

    async def get_work_package(self, wp_id: UUID) -> BizWorkPackage | None:
        wp = await self.db.get(BizWorkPackage, wp_id)
        if wp is None or wp.deleted_at is not None:
            return None
        return wp

    async def list_members(self, tenant_id: UUID, project_id: UUID) -> list[BizProjectMember]:
        stmt = (
            select(BizProjectMember)
            .where(
                BizProjectMember.tenant_id == tenant_id,
                BizProjectMember.project_id == project_id,
            )
            .order_by(BizProjectMember.role_in_project.asc())
        )
        return (await self.db.execute(stmt)).scalars().all()

    async def get_member(self, tenant_id: UUID, project_id: UUID, user_id: UUID) -> BizProjectMember | None:
        stmt = select(BizProjectMember).where(
            BizProjectMember.tenant_id == tenant_id,
            BizProjectMember.project_id == project_id,
            BizProjectMember.user_id == user_id,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()
