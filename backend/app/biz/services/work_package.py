"""工作包看板列表服务。"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.repositories.project import ProjectRepository
from app.biz.schemas.project import BizWorkPackageKanbanOut
from app.core.service import BaseService
from app.core.tenant import TenantContext


class WorkPackageService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.repo = ProjectRepository(db)

    async def list_kanban(
        self,
        *,
        project_id: UUID | None = None,
        service_line: str | None = None,
        status: str | None = None,
        limit: int = 200,
    ) -> list[BizWorkPackageKanbanOut]:
        rows = await self.repo.list_work_packages_filtered(
            self.ctx.tenant_id,
            project_id=project_id,
            service_line=service_line,
            status=status,
            limit=limit,
        )
        out: list[BizWorkPackageKanbanOut] = []
        for row in rows:
            wp, project_name, client_name = row
            out.append(BizWorkPackageKanbanOut(
                id=wp.id,
                project_id=wp.project_id,
                service_line=wp.service_line,
                name=wp.name,
                stage=wp.stage,
                stage_index=wp.stage_index,
                status=wp.status,
                owner_id=wp.owner_id,
                budget=wp.budget,
                actual_cost=wp.actual_cost,
                planned_start=wp.planned_start,
                planned_end=wp.planned_end,
                project_name=project_name or "",
                client_name=client_name or "",
            ))
        return out
