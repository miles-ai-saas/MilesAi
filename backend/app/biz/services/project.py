"""项目与工作包 CRUD 服务。

项目是交付的核心组织单元——一个项目包含多个按服务线拆分的工作包。
列表加载时采用批量预取优化：先分页查询项目，再一次性加载所有相关的工作包。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.audit import log_biz_action
from app.biz.repositories.project import ProjectRepository
from app.biz.schemas.project import (
    BizProjectCreate,
    BizProjectMemberCreate,
    BizProjectMemberOut,
    BizProjectOut,
    BizProjectUpdate,
    BizProjectCostSummaryOut,
    BizProjectCloseOut,
    BizWorkPackageCostLine,
    BizWorkPackageCreate,
    BizWorkPackageOut,
    BizWorkPackageUpdate,
    WorkPackageCreate,
)
from app.biz.services.service_line_template import ServiceLineTemplateService
from app.common.exceptions import BadRequestError, NotFoundError
from app.common.pagination import paginate
from app.common.schema import PageResult
from app.core.service import BaseService
from app.core.soft_delete import mark_deleted, not_deleted
from app.core.tenant import TenantContext, assert_tenant_access, tenant_filters
from app.models.biz import BizProject, BizProjectMember, BizWorkPackage
from app.models.biz.enums import ProjectStatus
from app.models.platform.user import User


class ProjectService(BaseService):
    """项目与工作包管理——支持关联创建、批量预取工作包。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.repo = ProjectRepository(db)
        self.template_svc = ServiceLineTemplateService(db)

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
            await self._add_work_package(row.id, wp_body)

        await log_biz_action(
            self.db, self.ctx,
            action="biz.project.create",
            resource_type="biz_project",
            resource_id=row.id,
            detail={"name": row.name, "work_package_count": len(body.work_packages)},
        )

        wps = await self.repo.get_work_packages(self.ctx.tenant_id, row.id)
        return self._to_out(row, wps)

    async def update_project(self, project_id: UUID, body: BizProjectUpdate) -> BizProjectOut:
        """更新项目（仅更新传入的非空字段）。"""
        row = await self._get_or_raise(project_id)
        changed: list[str] = []
        for f in ("name", "code", "status", "owner_id", "description", "total_budget"):
            val = getattr(body, f, None)
            if val is not None:
                setattr(row, f, val.strip() if isinstance(val, str) and f in ("name", "code") else val)
                changed.append(f)
        await self.db.flush()
        if changed:
            await log_biz_action(
                self.db, self.ctx,
                action="biz.project.update",
                resource_type="biz_project",
                resource_id=row.id,
                detail={"fields": changed},
            )
        return await self.get_project(project_id)

    async def delete_project(self, project_id: UUID) -> None:
        """软删除项目，不影响关联的工作包。"""
        row = await self._get_or_raise(project_id)
        await mark_deleted(self.db, row)
        await log_biz_action(
            self.db, self.ctx,
            action="biz.project.delete",
            resource_type="biz_project",
            resource_id=row.id,
            detail={"name": row.name},
        )

    # ── work packages ──

    async def list_work_packages(self, project_id: UUID) -> list[BizWorkPackageOut]:
        """列出项目下的工作包（按阶段序号排序）。"""
        await self._get_or_raise(project_id)
        rows = await self.repo.get_work_packages(self.ctx.tenant_id, project_id)
        return [self._wp_to_out(r) for r in rows]

    async def create_work_package(self, project_id: UUID, body: BizWorkPackageCreate) -> BizWorkPackageOut:
        """在项目下创建工作包。"""
        await self._get_or_raise(project_id)
        wp = await self._add_work_package(project_id, body)
        await log_biz_action(
            self.db, self.ctx,
            action="biz.work_package.create",
            resource_type="biz_work_package",
            resource_id=wp.id,
            detail={"project_id": str(project_id), "service_line": wp.service_line, "name": wp.name},
        )
        return self._wp_to_out(wp)

    async def update_work_package(self, wp_id: UUID, body: BizWorkPackageUpdate) -> BizWorkPackageOut:
        """更新工作包信息。"""
        wp = await self.repo.get_work_package(wp_id)
        if not wp:
            raise NotFoundError("工作包不存在")
        assert_tenant_access(self.ctx, wp.tenant_id)
        old_status = wp.status
        for f in ("name", "stage", "status", "owner_id", "budget", "actual_cost", "planned_start", "planned_end"):
            val = getattr(body, f, None)
            if val is not None:
                setattr(wp, f, val.strip() if isinstance(val, str) else val)
        await self.db.flush()
        await self.db.refresh(wp)
        if body.status is not None and body.status != old_status:
            await log_biz_action(
                self.db, self.ctx,
                action="biz.work_package.status_change",
                resource_type="biz_work_package",
                resource_id=wp.id,
                detail={"from": old_status, "to": body.status, "project_id": str(wp.project_id)},
            )
        return self._wp_to_out(wp)

    async def delete_work_package(self, wp_id: UUID) -> None:
        """软删除工作包。"""
        wp = await self.repo.get_work_package(wp_id)
        if not wp:
            raise NotFoundError("工作包不存在")
        assert_tenant_access(self.ctx, wp.tenant_id)
        await mark_deleted(self.db, wp)
        await log_biz_action(
            self.db, self.ctx,
            action="biz.work_package.delete",
            resource_type="biz_work_package",
            resource_id=wp.id,
            detail={"project_id": str(wp.project_id), "name": wp.name},
        )

    # ── members ──

    async def list_members(self, project_id: UUID) -> list[BizProjectMemberOut]:
        await self._get_or_raise(project_id)
        rows = await self.repo.list_members(self.ctx.tenant_id, project_id)
        if not rows:
            return []
        user_ids = [r.user_id for r in rows]
        users = {
            u.id: u.username
            for u in (await self.db.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
        }
        return [
            BizProjectMemberOut(
                project_id=r.project_id,
                user_id=r.user_id,
                role_in_project=r.role_in_project,
                username=users.get(r.user_id),
            )
            for r in rows
        ]

    async def add_member(self, project_id: UUID, body: BizProjectMemberCreate) -> BizProjectMemberOut:
        await self._get_or_raise(project_id)
        user = await self.db.get(User, body.user_id)
        if not user or user.tenant_id != self.ctx.tenant_id:
            raise BadRequestError("用户不存在或不属于当前租户")
        existing = await self.repo.get_member(self.ctx.tenant_id, project_id, body.user_id)
        if existing:
            raise BadRequestError("用户已是项目成员")
        row = BizProjectMember(
            tenant_id=self.ctx.tenant_id,
            project_id=project_id,
            user_id=body.user_id,
            role_in_project=body.role_in_project or "viewer",
        )
        self.db.add(row)
        await self.db.flush()
        await log_biz_action(
            self.db, self.ctx,
            action="biz.project.member.add",
            resource_type="biz_project",
            resource_id=project_id,
            detail={"user_id": str(body.user_id), "role": row.role_in_project},
        )
        return BizProjectMemberOut(
            project_id=project_id,
            user_id=body.user_id,
            role_in_project=row.role_in_project,
            username=user.username,
        )

    async def remove_member(self, project_id: UUID, user_id: UUID) -> None:
        await self._get_or_raise(project_id)
        row = await self.repo.get_member(self.ctx.tenant_id, project_id, user_id)
        if not row:
            raise NotFoundError("项目成员不存在")
        await self.db.delete(row)
        await self.db.flush()
        await log_biz_action(
            self.db, self.ctx,
            action="biz.project.member.remove",
            resource_type="biz_project",
            resource_id=project_id,
            detail={"user_id": str(user_id)},
        )

    async def advance_work_package_stage(self, wp_id: UUID) -> BizWorkPackageOut:
        """按服务线模板推进工作包到下一阶段。"""
        wp = await self.repo.get_work_package(wp_id)
        if not wp:
            raise NotFoundError("工作包不存在")
        assert_tenant_access(self.ctx, wp.tenant_id)

        nxt = await self.template_svc.next_stage(self.ctx.tenant_id, wp.service_line, wp.stage_index)
        if nxt is None:
            raise BadRequestError("已在最后阶段，无法继续推进")

        old_stage, old_index = wp.stage, wp.stage_index
        wp.stage, wp.stage_index = nxt
        await self.db.flush()
        await self.db.refresh(wp)
        await log_biz_action(
            self.db, self.ctx,
            action="biz.work_package.advance_stage",
            resource_type="biz_work_package",
            resource_id=wp.id,
            detail={
                "project_id": str(wp.project_id),
                "from_stage": old_stage,
                "from_index": old_index,
                "to_stage": wp.stage,
                "to_index": wp.stage_index,
            },
        )
        return self._wp_to_out(wp)

    async def get_cost_summary(self, project_id: UUID) -> BizProjectCostSummaryOut:
        """汇总项目与各工作包预算/实际成本。"""
        row = await self._get_or_raise(project_id)
        wps = await self.repo.get_work_packages(self.ctx.tenant_id, project_id)

        budget_total = sum(w.budget or 0 for w in wps) if wps else None
        actual_total = sum(w.actual_cost or 0 for w in wps) if wps else None
        variance = None
        if row.total_budget is not None and actual_total is not None:
            variance = row.total_budget - actual_total

        lines = [
            BizWorkPackageCostLine(
                id=w.id,
                name=w.name,
                service_line=w.service_line,
                budget=w.budget,
                actual_cost=w.actual_cost,
                variance=(w.budget - w.actual_cost) if w.budget is not None and w.actual_cost is not None else None,
            )
            for w in wps
        ]

        return BizProjectCostSummaryOut(
            project_id=row.id,
            total_budget=row.total_budget,
            work_package_budget_total=budget_total,
            work_package_actual_total=actual_total,
            budget_variance=variance,
            work_packages=lines,
        )

    async def close_project(self, project_id: UUID) -> BizProjectCloseOut:
        """结项：将项目状态置为 closed。"""
        row = await self._get_or_raise(project_id)
        if row.status == ProjectStatus.CLOSED.value:
            raise BadRequestError("项目已结项")
        if row.status == ProjectStatus.CANCELLED.value:
            raise BadRequestError("已取消的项目不能结项")

        old_status = row.status
        row.status = ProjectStatus.CLOSED.value
        await self.db.flush()
        await log_biz_action(
            self.db, self.ctx,
            action="biz.project.close",
            resource_type="biz_project",
            resource_id=row.id,
            detail={"from": old_status, "to": row.status},
        )
        return BizProjectCloseOut(id=row.id, status=row.status)

    # ── internal ──

    async def _add_work_package(self, project_id: UUID, body: WorkPackageCreate | BizWorkPackageCreate) -> BizWorkPackage:
        stage, stage_index = await self.template_svc.resolve_initial_stage(self.ctx.tenant_id, body.service_line)
        wp = BizWorkPackage(
            tenant_id=self.ctx.tenant_id,
            project_id=project_id,
            service_line=body.service_line,
            name=body.name.strip(),
            stage=stage,
            stage_index=stage_index,
            owner_id=body.owner_id,
            budget=body.budget,
            planned_start=body.planned_start,
            planned_end=body.planned_end,
        )
        self.db.add(wp)
        await self.db.flush()
        await self.db.refresh(wp)
        return wp

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

    def _wp_to_out(self, r: BizWorkPackage) -> BizWorkPackageOut:
        return BizWorkPackageOut(
            id=r.id, project_id=r.project_id, service_line=r.service_line, name=r.name,
            stage=r.stage, stage_index=r.stage_index, status=r.status, owner_id=r.owner_id,
            budget=r.budget, actual_cost=r.actual_cost, planned_start=r.planned_start, planned_end=r.planned_end,
        )

    def _to_out(self, row: BizProject, wps: list[BizWorkPackage]) -> BizProjectOut:
        return BizProjectOut(
            id=row.id, client_id=row.client_id, name=row.name, status=row.status,
            code=row.code, owner_id=row.owner_id, description=row.description,
            total_budget=row.total_budget,
            work_packages=[self._wp_to_out(r) for r in wps],
        )
