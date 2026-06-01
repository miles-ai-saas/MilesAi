"""供应商 CRUD 与项目关联服务。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.audit import log_biz_action
from app.biz.repositories.project import ProjectRepository
from app.biz.repositories.supplier import SupplierRepository
from app.biz.schemas.supplier import (
    BizProjectSupplierCreate,
    BizProjectSupplierOut,
    BizProjectSupplierUpdate,
    BizSupplierContactCreate,
    BizSupplierContactOut,
    BizSupplierCreate,
    BizSupplierOut,
    BizSupplierUpdate,
)
from app.common.exceptions import BadRequestError, NotFoundError
from app.common.pagination import paginate
from app.common.schema import PageResult
from app.core.service import BaseService
from app.core.soft_delete import is_marked_deleted, mark_deleted, not_deleted
from app.core.tenant import TenantContext, assert_tenant_access, tenant_filters
from app.models.biz import BizProjectSupplier, BizSupplier, BizSupplierContact


class SupplierService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.repo = SupplierRepository(db)
        self.project_repo = ProjectRepository(db)

    async def list_suppliers(
        self,
        *,
        page: int = 1,
        size: int = 20,
        search: str | None = None,
        category: str | None = None,
        status: str | None = None,
    ) -> PageResult[BizSupplierOut]:
        filters = tenant_filters(self.ctx, BizSupplier.tenant_id)
        if search:
            filters.append(BizSupplier.name.ilike(f"%{search}%"))
        if category:
            filters.append(BizSupplier.category == category)
        if status:
            filters.append(BizSupplier.status == status)
        result = await paginate(
            self.db, BizSupplier, page=page, size=size,
            filters=filters, order_by=BizSupplier.name.asc(),
        )

        supplier_ids = [r.id for r in result.items]
        project_counts = await self.repo.get_project_counts(self.ctx.tenant_id, supplier_ids)
        contacts_map = await self.repo.get_contacts_for_suppliers(self.ctx.tenant_id, supplier_ids)

        return PageResult(
            items=[self._to_out(r, project_counts.get(r.id, 0), contacts_map.get(r.id, [])) for r in result.items],
            total=result.total, page=result.page, size=result.size,
        )

    async def get_supplier(self, supplier_id: UUID) -> BizSupplierOut:
        row = await self._get_or_raise(supplier_id)
        project_counts = await self.repo.get_project_counts(self.ctx.tenant_id, [supplier_id])
        contacts = await self.repo.get_contacts(self.ctx.tenant_id, supplier_id)
        return self._to_out(row, project_counts.get(supplier_id, 0), contacts)

    async def create_supplier(self, body: BizSupplierCreate) -> BizSupplierOut:
        row = BizSupplier(
            tenant_id=self.ctx.tenant_id,
            name=body.name.strip(),
            short_name=body.short_name.strip() if body.short_name else None,
            category=body.category or "other",
            status=body.status or "active",
            contact_name=body.contact_name,
            contact_phone=body.contact_phone,
            contact_email=body.contact_email,
            address=body.address,
            bank_name=body.bank_name,
            bank_account=body.bank_account,
            remark=body.remark,
            created_by=self.ctx.user_id,
        )
        self.db.add(row)
        await self.db.flush()
        await log_biz_action(
            self.db, self.ctx,
            action="biz.supplier.create",
            resource_type="biz_supplier",
            resource_id=row.id,
            detail={"name": row.name, "category": row.category},
        )
        return self._to_out(row, 0, [])

    async def update_supplier(self, supplier_id: UUID, body: BizSupplierUpdate) -> BizSupplierOut:
        row = await self._get_or_raise(supplier_id)
        changed: list[str] = []
        for f in (
            "name", "short_name", "category", "status", "contact_name", "contact_phone",
            "contact_email", "address", "bank_name", "bank_account", "remark",
        ):
            val = getattr(body, f, None)
            if val is not None:
                setattr(row, f, val.strip() if isinstance(val, str) and f in ("name", "short_name") else val)
                changed.append(f)
        await self.db.flush()
        if changed:
            await log_biz_action(
                self.db, self.ctx,
                action="biz.supplier.update",
                resource_type="biz_supplier",
                resource_id=row.id,
                detail={"fields": changed},
            )
        return await self.get_supplier(supplier_id)

    async def delete_supplier(self, supplier_id: UUID) -> None:
        row = await self._get_or_raise(supplier_id)
        await mark_deleted(self.db, row)
        await log_biz_action(
            self.db, self.ctx,
            action="biz.supplier.delete",
            resource_type="biz_supplier",
            resource_id=row.id,
            detail={"name": row.name},
        )

    # ── contacts ──

    async def list_contacts(self, supplier_id: UUID) -> list[BizSupplierContactOut]:
        await self._get_or_raise(supplier_id)
        rows = await self.repo.get_contacts(self.ctx.tenant_id, supplier_id)
        return [self._contact_to_out(c) for c in rows]

    async def create_contact(self, supplier_id: UUID, body: BizSupplierContactCreate) -> BizSupplierContactOut:
        await self._get_or_raise(supplier_id)
        if body.is_primary:
            await self._clear_primary(supplier_id)
        row = BizSupplierContact(
            tenant_id=self.ctx.tenant_id,
            supplier_id=supplier_id,
            name=body.name.strip(),
            title=body.title,
            phone=body.phone,
            email=body.email,
            is_primary=body.is_primary,
        )
        self.db.add(row)
        await self.db.flush()
        return self._contact_to_out(row)

    async def update_contact(self, contact_id: UUID, body: BizSupplierContactCreate) -> BizSupplierContactOut:
        row = await self.repo.get_contact(contact_id)
        if not row or is_marked_deleted(row):
            raise NotFoundError("联系人不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        if body.is_primary and not row.is_primary:
            await self._clear_primary(row.supplier_id)
        row.name = body.name.strip()
        row.title = body.title
        row.phone = body.phone
        row.email = body.email
        row.is_primary = body.is_primary
        await self.db.flush()
        return self._contact_to_out(row)

    async def delete_contact(self, contact_id: UUID) -> None:
        row = await self.repo.get_contact(contact_id)
        if not row or is_marked_deleted(row):
            raise NotFoundError("联系人不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        await mark_deleted(self.db, row)

    # ── project suppliers ──

    async def list_project_suppliers(self, project_id: UUID) -> list[BizProjectSupplierOut]:
        await self._ensure_project(project_id)
        rows = await self.repo.list_project_suppliers(self.ctx.tenant_id, project_id)
        return [self._ps_to_out(ps, supplier) for ps, supplier in rows]

    async def add_project_supplier(self, project_id: UUID, body: BizProjectSupplierCreate) -> BizProjectSupplierOut:
        await self._ensure_project(project_id)
        supplier = await self._get_or_raise(body.supplier_id)
        existing = await self.repo.get_project_supplier(self.ctx.tenant_id, project_id, body.supplier_id)
        if existing:
            raise BadRequestError("该供应商已关联此项目")
        if body.work_package_id:
            wp = await self.project_repo.get_work_package(body.work_package_id)
            if not wp or wp.project_id != project_id:
                raise BadRequestError("工作包不存在或不属于该项目")
        row = BizProjectSupplier(
            tenant_id=self.ctx.tenant_id,
            project_id=project_id,
            supplier_id=body.supplier_id,
            work_package_id=body.work_package_id,
            role_description=body.role_description,
            contracted_amount=body.contracted_amount,
            status=body.status or "active",
            remark=body.remark,
        )
        self.db.add(row)
        await self.db.flush()
        await log_biz_action(
            self.db, self.ctx,
            action="biz.project.supplier.add",
            resource_type="biz_project",
            resource_id=project_id,
            detail={"supplier_id": str(body.supplier_id), "role": body.role_description},
        )
        return self._ps_to_out(row, supplier)

    async def update_project_supplier(
        self, project_id: UUID, supplier_id: UUID, body: BizProjectSupplierUpdate,
    ) -> BizProjectSupplierOut:
        await self._ensure_project(project_id)
        supplier = await self._get_or_raise(supplier_id)
        row = await self.repo.get_project_supplier(self.ctx.tenant_id, project_id, supplier_id)
        if not row:
            raise NotFoundError("项目供应商关联不存在")
        if body.work_package_id is not None:
            if body.work_package_id:
                wp = await self.project_repo.get_work_package(body.work_package_id)
                if not wp or wp.project_id != project_id:
                    raise BadRequestError("工作包不存在或不属于该项目")
            row.work_package_id = body.work_package_id
        for f in ("role_description", "contracted_amount", "status", "remark"):
            val = getattr(body, f, None)
            if val is not None:
                setattr(row, f, val)
        await self.db.flush()
        return self._ps_to_out(row, supplier)

    async def remove_project_supplier(self, project_id: UUID, supplier_id: UUID) -> None:
        await self._ensure_project(project_id)
        row = await self.repo.get_project_supplier(self.ctx.tenant_id, project_id, supplier_id)
        if not row:
            raise NotFoundError("项目供应商关联不存在")
        await self.db.delete(row)
        await self.db.flush()
        await log_biz_action(
            self.db, self.ctx,
            action="biz.project.supplier.remove",
            resource_type="biz_project",
            resource_id=project_id,
            detail={"supplier_id": str(supplier_id)},
        )

    async def _ensure_project(self, project_id: UUID) -> None:
        row = await self.project_repo.get_by_id(project_id)
        if not row:
            raise NotFoundError("项目不存在")
        assert_tenant_access(self.ctx, row.tenant_id)

    async def _get_or_raise(self, supplier_id: UUID) -> BizSupplier:
        row = await self.repo.get_by_id(supplier_id)
        if not row:
            raise NotFoundError("供应商不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        return row

    async def _clear_primary(self, supplier_id: UUID) -> None:
        for c in await self.repo.get_contacts(self.ctx.tenant_id, supplier_id):
            if c.is_primary:
                c.is_primary = False

    def _contact_to_out(self, c: BizSupplierContact) -> BizSupplierContactOut:
        return BizSupplierContactOut(
            id=c.id, supplier_id=c.supplier_id, name=c.name,
            title=c.title, phone=c.phone, email=c.email, is_primary=c.is_primary,
        )

    def _ps_to_out(self, ps: BizProjectSupplier, supplier: BizSupplier) -> BizProjectSupplierOut:
        return BizProjectSupplierOut(
            project_id=ps.project_id,
            supplier_id=ps.supplier_id,
            supplier_name=supplier.name,
            supplier_category=supplier.category,
            work_package_id=ps.work_package_id,
            role_description=ps.role_description,
            contracted_amount=ps.contracted_amount,
            status=ps.status,
            remark=ps.remark,
        )

    def _to_out(self, row: BizSupplier, project_count: int, contacts: list[BizSupplierContact]) -> BizSupplierOut:
        return BizSupplierOut(
            id=row.id,
            name=row.name,
            short_name=row.short_name,
            category=row.category,
            status=row.status,
            contact_name=row.contact_name,
            contact_phone=row.contact_phone,
            contact_email=row.contact_email,
            address=row.address,
            bank_name=row.bank_name,
            bank_account=row.bank_account,
            remark=row.remark,
            project_count=project_count,
            contacts=[self._contact_to_out(c) for c in contacts],
        )
