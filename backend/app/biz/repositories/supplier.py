"""供应商仓储。"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import BaseRepository
from app.core.soft_delete import not_deleted
from app.models.biz import BizProject, BizProjectSupplier, BizSupplier, BizSupplierContact


class SupplierRepository(BaseRepository[BizSupplier]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, BizSupplier)

    async def get_project_counts(self, tenant_id: UUID, supplier_ids: list[UUID]) -> dict[UUID, int]:
        if not supplier_ids:
            return {}
        stmt = (
            select(BizProjectSupplier.supplier_id, func.count(BizProjectSupplier.project_id))
            .where(
                BizProjectSupplier.tenant_id == tenant_id,
                BizProjectSupplier.supplier_id.in_(supplier_ids),
            )
            .group_by(BizProjectSupplier.supplier_id)
        )
        return dict((await self.db.execute(stmt)).all())

    async def get_contacts(self, tenant_id: UUID, supplier_id: UUID) -> list[BizSupplierContact]:
        stmt = (
            select(BizSupplierContact)
            .where(
                BizSupplierContact.tenant_id == tenant_id,
                BizSupplierContact.supplier_id == supplier_id,
                not_deleted(BizSupplierContact),
            )
            .order_by(BizSupplierContact.is_primary.desc(), BizSupplierContact.name.asc())
        )
        return (await self.db.execute(stmt)).scalars().all()

    async def get_contacts_for_suppliers(self, tenant_id: UUID, supplier_ids: list[UUID]) -> dict[UUID, list[BizSupplierContact]]:
        if not supplier_ids:
            return {}
        stmt = (
            select(BizSupplierContact)
            .where(
                BizSupplierContact.tenant_id == tenant_id,
                BizSupplierContact.supplier_id.in_(supplier_ids),
                not_deleted(BizSupplierContact),
            )
            .order_by(BizSupplierContact.is_primary.desc(), BizSupplierContact.name.asc())
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        out: dict[UUID, list[BizSupplierContact]] = {}
        for r in rows:
            out.setdefault(r.supplier_id, []).append(r)
        return out

    async def get_contact(self, contact_id: UUID) -> BizSupplierContact | None:
        return await self.db.get(BizSupplierContact, contact_id)

    async def list_project_suppliers(self, tenant_id: UUID, project_id: UUID) -> list[tuple[BizProjectSupplier, BizSupplier]]:
        stmt = (
            select(BizProjectSupplier, BizSupplier)
            .join(BizSupplier, BizSupplier.id == BizProjectSupplier.supplier_id)
            .where(
                BizProjectSupplier.tenant_id == tenant_id,
                BizProjectSupplier.project_id == project_id,
                not_deleted(BizSupplier),
            )
            .order_by(BizSupplier.name.asc())
        )
        return (await self.db.execute(stmt)).all()

    async def get_project_supplier(self, tenant_id: UUID, project_id: UUID, supplier_id: UUID) -> BizProjectSupplier | None:
        stmt = select(BizProjectSupplier).where(
            BizProjectSupplier.tenant_id == tenant_id,
            BizProjectSupplier.project_id == project_id,
            BizProjectSupplier.supplier_id == supplier_id,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_supplier_projects(self, tenant_id: UUID, supplier_id: UUID) -> list[tuple[BizProjectSupplier, BizProject]]:
        stmt = (
            select(BizProjectSupplier, BizProject)
            .join(BizProject, BizProject.id == BizProjectSupplier.project_id)
            .where(
                BizProjectSupplier.tenant_id == tenant_id,
                BizProjectSupplier.supplier_id == supplier_id,
                not_deleted(BizProject),
            )
            .order_by(BizProject.name.asc())
        )
        return (await self.db.execute(stmt)).all()
