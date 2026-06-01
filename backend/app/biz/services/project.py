"""项目与工作包 CRUD 服务。

项目是交付的核心组织单元——一个项目包含多个按服务线拆分的工作包。
列表加载时采用批量预取优化：先分页查询项目，再一次性加载所有相关的工作包。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.repositories.project import ProjectRepository
from app.biz.schemas.project import (
    BizProjectCreate,
    BizProjectOut,
    BizProjectUpdate,
    BizWorkPackageOut,
    BizWorkPackageUpdate,
)
from app.common.exceptions import NotFoundError
from app.common.pagination import paginate
from app.common.schema import PageResult
from app.core.service import BaseService
from app.core.soft_delete import mark_deleted, not_deleted
from app.core.tenant import TenantContext, assert_tenant_access, tenant_filters
from app.models.biz import BizProject, BizWorkPackage


class ProjectService(BaseService):
    """项目与工作包管理——支持关联创建、批量预取工作包。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.repo = ProjectRepository(db)

    # ── projects ──

    async def list_projects(
        self, *, page: int = 1, size: int = 20, client_id: UUID | None = None, status: str | None = None,
    ) -> PageResult[BizProjectOut]:
        """分页查询项目，批量预取工作包避免 N+1。"""
        filters = tenant_filters(self.ctx, BizProject.tenant_id)
        if client_id:
            filters.append(BizProject.client_id == client_id)
        if status:
            filters.append(BizProject.status == status)
        result = await paginate(
            self.db, BizProject, page=page, size=size,
            filters=filters, order_by=BizProject.name.asc(),
        )

        project_ids = [r.id for r in result.items]
        wps = await self._load_work_packages_batch(project_ids) if project_ids else {}

        return PageResult(
            items=[self._to_out(r, wps.get(r.id, [])) for r in result.items],
            total=result.total, page=result.page, size=result.size,
        )

    async def get_project(self, project_id: UUID) -> BizProjectOut:
        """获取单个项目及其工作包。"""
        row = await self._get_or_raise(project_id)
        wps = await self.repo.get_work_packages(self.ctx.tenant_id, project_id)
        return self._to_out(row, wps)

    async def create_project(self, body: BizProjectCreate) -> BizProjectOut:
        """创建项目，可同时创建多个关联工作包（事务内完成）。"""
        row = BizProject(
            tenant_id=self.ctx.tenant_id,
            client_id=body.client_id,
            name=body.name.strip(),
            code=body.code.strip() if body.code else None,
            owner_id=body.owner_id,
            description=body.description,
            total_budget=body.total_budget,
            created_by=self.ctx.user_id,
        )
        self.db.add(row)
        await self.db.flush()

        for wp_body in body.work_packages:
            wp = BizWorkPackage(
                tenant_id=self.ctx.tenant_id,
                project_id=row.id,
                service_line=wp_body.service_line,
                name=wp_body.name.strip(),
                owner_id=wp_body.owner_id,
                budget=wp_body.budget,
                planned_start=wp_body.planned_start,
                planned_end=wp_body.planned_end,
            )
            self.db.add(wp)
        await self.db.flush()

        wps = await self.repo.get_work_packages(self.ctx.tenant_id, row.id)
        return self._to_out(row, wps)

    async def update_project(self, project_id: UUID, body: BizProjectUpdate) -> BizProjectOut:
        """更新项目（仅更新传入的非空字段）。"""
        row = await self._get_or_raise(project_id)
        for f in ("name", "code", "status", "owner_id", "description", "total_budget"):
            val = getattr(body, f, None)
            if val is not None:
                setattr(row, f, val.strip() if isinstance(val, str) and f in ("name", "code") else val)
        await self.db.flush()
        return await self.get_project(project_id)

    async def delete_project(self, project_id: UUID) -> None:
        """软删除项目，不影响关联的工作包。"""
        row = await self._get_or_raise(project_id)
        await mark_deleted(self.db, row)

    # ── work packages ──

    async def list_work_packages(self, project_id: UUID) -> list[BizWorkPackageOut]:
        """列出项目下的工作包（按阶段序号排序）。"""
        await self._get_or_raise(project_id)
        rows = await self.repo.get_work_packages(self.ctx.tenant_id, project_id)
        return [BizWorkPackageOut(id=r.id, project_id=r.project_id, service_line=r.service_line, name=r.name, stage=r.stage, stage_index=r.stage_index, status=r.status, owner_id=r.owner_id, budget=r.budget, actual_cost=r.actual_cost, planned_start=r.planned_start, planned_end=r.planned_end) for r in rows]

    async def create_work_package(self, project_id: UUID, body: BizWorkPackageUpdate) -> BizWorkPackageOut:
        """在项目下创建工作包。"""
        await self._get_or_raise(project_id)
        wp = BizWorkPackage(
            tenant_id=self.ctx.tenant_id, project_id=project_id,
            service_line=body.name or "other", name=body.name or "未命名",
            stage=body.stage, status=body.status or "pending",
            owner_id=body.owner_id, budget=body.budget,
            actual_cost=body.actual_cost,
            planned_start=body.planned_start, planned_end=body.planned_end,
        )
        self.db.add(wp)
        await self.db.flush()
        await self.db.refresh(wp)
        return BizWorkPackageOut(id=wp.id, project_id=wp.project_id, service_line=wp.service_line, name=wp.name, stage=wp.stage, stage_index=wp.stage_index, status=wp.status, owner_id=wp.owner_id, budget=wp.budget, actual_cost=wp.actual_cost, planned_start=wp.planned_start, planned_end=wp.planned_end)

    async def update_work_package(self, wp_id: UUID, body: BizWorkPackageUpdate) -> BizWorkPackageOut:
        """更新工作包信息。"""
        wp = await self.repo.get_work_package(wp_id)
        if not wp:
            raise NotFoundError("工作包不存在")
        assert_tenant_access(self.ctx, wp.tenant_id)
        for f in ("name", "stage", "status", "owner_id", "budget", "actual_cost", "planned_start", "planned_end"):
            val = getattr(body, f, None)
            if val is not None:
                setattr(wp, f, val.strip() if isinstance(val, str) else val)
        await self.db.flush()
        await self.db.refresh(wp)
        return BizWorkPackageOut(id=wp.id, project_id=wp.project_id, service_line=wp.service_line, name=wp.name, stage=wp.stage, stage_index=wp.stage_index, status=wp.status, owner_id=wp.owner_id, budget=wp.budget, actual_cost=wp.actual_cost, planned_start=wp.planned_start, planned_end=wp.planned_end)

    async def delete_work_package(self, wp_id: UUID) -> None:
        """软删除工作包。"""
        wp = await self.repo.get_work_package(wp_id)
        if not wp:
            raise NotFoundError("工作包不存在")
        assert_tenant_access(self.ctx, wp.tenant_id)
        await mark_deleted(self.db, wp)

    # ── internal ──

    async def _get_or_raise(self, project_id: UUID) -> BizProject:
        row = await self.repo.get_by_id(project_id)
        if not row:
            raise NotFoundError("项目不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        return row

    async def _load_work_packages_batch(self, project_ids: list[UUID]) -> dict[UUID, list[BizWorkPackage]]:
        """批量预取：一次查询加载所有项目的工作包，按 project_id 分组。"""
        stmt = (
            select(BizWorkPackage)
            .where(
                BizWorkPackage.tenant_id == self.ctx.tenant_id,
                BizWorkPackage.project_id.in_(project_ids),
                not_deleted(BizWorkPackage),
            )
            .order_by(BizWorkPackage.stage_index.asc())
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        out: dict[UUID, list[BizWorkPackage]] = {}
        for r in rows:
            out.setdefault(r.project_id, []).append(r)
        return out

    def _to_out(self, row: BizProject, wps: list[BizWorkPackage]) -> BizProjectOut:
        return BizProjectOut(
            id=row.id, client_id=row.client_id, name=row.name, status=row.status,
            code=row.code, owner_id=row.owner_id, description=row.description,
            total_budget=row.total_budget,
            work_packages=[BizWorkPackageOut(id=r.id, project_id=r.project_id, service_line=r.service_line, name=r.name, stage=r.stage, stage_index=r.stage_index, status=r.status, owner_id=r.owner_id, budget=r.budget, actual_cost=r.actual_cost, planned_start=r.planned_start, planned_end=r.planned_end) for r in wps],
        )
