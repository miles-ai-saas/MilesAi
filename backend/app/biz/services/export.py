"""业务中心 CSV 导出。"""

from __future__ import annotations

import csv
import io
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.service import BaseService
from app.core.soft_delete import not_deleted
from app.core.tenant import TenantContext, tenant_filters
from app.models.biz import BizClient, BizContract, BizOpportunity, BizPayment, BizProject


def _csv_text(rows: list[list[str]]) -> str:
    buf = io.StringIO()
    buf.write("\ufeff")
    writer = csv.writer(buf)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


class BizExportService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)

    async def export_projects_csv(self, *, client_id: UUID | None = None, status: str | None = None) -> str:
        filters = tenant_filters(self.ctx, BizProject.tenant_id) + [not_deleted(BizProject)]
        if client_id:
            filters.append(BizProject.client_id == client_id)
        if status:
            filters.append(BizProject.status == status)
        stmt = (
            select(BizProject, BizClient.name.label("client_name"))
            .join(BizClient, BizClient.id == BizProject.client_id, isouter=True)
            .where(*filters)
            .order_by(BizProject.updated_at.desc())
            .limit(5000)
        )
        rows = (await self.db.execute(stmt)).all()
        data = [["项目编号", "项目名称", "客户", "状态", "总预算", "描述"]]
        for r in rows:
            p = r.BizProject
            data.append([
                p.code or "",
                p.name,
                r.client_name or "",
                p.status,
                str(p.total_budget) if p.total_budget is not None else "",
                (p.description or "").replace("\n", " "),
            ])
        return _csv_text(data)

    async def export_opportunities_csv(self, *, client_id: UUID | None = None, stage: str | None = None) -> str:
        filters = tenant_filters(self.ctx, BizOpportunity.tenant_id) + [not_deleted(BizOpportunity)]
        if client_id:
            filters.append(BizOpportunity.client_id == client_id)
        if stage:
            filters.append(BizOpportunity.stage == stage)
        stmt = (
            select(BizOpportunity, BizClient.name.label("client_name"))
            .join(BizClient, BizClient.id == BizOpportunity.client_id, isouter=True)
            .where(*filters)
            .order_by(BizOpportunity.updated_at.desc())
            .limit(5000)
        )
        rows = (await self.db.execute(stmt)).all()
        data = [["商机名称", "客户", "阶段", "预估金额", "赢单概率", "预计结单", "描述"]]
        for r in rows:
            o = r.BizOpportunity
            data.append([
                o.name,
                r.client_name or "",
                o.stage,
                str(o.expected_value) if o.expected_value is not None else "",
                str(o.probability) if o.probability is not None else "",
                o.expected_close_date or "",
                (o.description or "").replace("\n", " "),
            ])
        return _csv_text(data)

    async def export_clients_csv(self, *, search: str | None = None) -> str:
        filters = tenant_filters(self.ctx, BizClient.tenant_id) + [not_deleted(BizClient)]
        if search:
            filters.append(BizClient.name.ilike(f"%{search}%"))
        stmt = (
            select(BizClient)
            .where(*filters)
            .order_by(BizClient.updated_at.desc())
            .limit(5000)
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        data = [["客户名称", "简称", "行业", "保密级别", "地址", "备注"]]
        for c in rows:
            data.append([
                c.name,
                c.short_name or "",
                c.industry or "",
                c.confidentiality_level,
                c.address or "",
                (c.remark or "").replace("\n", " "),
            ])
        return _csv_text(data)

    async def export_contracts_csv(
        self,
        *,
        client_id: UUID | None = None,
        status: str | None = None,
    ) -> str:
        filters = tenant_filters(self.ctx, BizContract.tenant_id) + [not_deleted(BizContract)]
        if client_id:
            filters.append(BizContract.client_id == client_id)
        if status:
            filters.append(BizContract.status == status)
        stmt = (
            select(BizContract, BizClient.name.label("client_name"), BizProject.name.label("project_name"))
            .join(BizClient, BizClient.id == BizContract.client_id, isouter=True)
            .join(BizProject, BizProject.id == BizContract.project_id, isouter=True)
            .where(*filters)
            .order_by(BizContract.updated_at.desc())
            .limit(5000)
        )
        rows = (await self.db.execute(stmt)).all()
        data = [["合同名称", "合同编号", "客户", "项目", "类型", "状态", "金额", "签署日期", "开始", "结束"]]
        for r in rows:
            c = r.BizContract
            data.append([
                c.name,
                c.contract_no or "",
                r.client_name or "",
                r.project_name or "",
                c.type,
                c.status,
                str(c.total_amount) if c.total_amount is not None else "",
                c.signed_date or "",
                c.start_date or "",
                c.end_date or "",
            ])
        return _csv_text(data)

    async def export_payments_csv(self) -> str:
        filters = tenant_filters(self.ctx, BizPayment.tenant_id) + [not_deleted(BizPayment)]
        stmt = (
            select(BizPayment, BizContract.name.label("contract_name"))
            .join(BizContract, BizContract.id == BizPayment.contract_id, isouter=True)
            .where(*filters)
            .order_by(BizPayment.planned_date.desc().nullslast(), BizPayment.updated_at.desc())
            .limit(5000)
        )
        rows = (await self.db.execute(stmt)).all()
        data = [["摘要", "合同", "方向", "金额", "状态", "计划日期", "实付日期", "备注"]]
        for r in rows:
            p = r.BizPayment
            data.append([
                p.name,
                r.contract_name or "",
                p.direction,
                str(p.amount),
                p.status,
                p.planned_date or "",
                p.paid_date or "",
                (p.remark or "").replace("\n", " "),
            ])
        return _csv_text(data)
