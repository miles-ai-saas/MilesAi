"""客户仓储（biz_clients 分页与 CRUD）。"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import BaseRepository
from app.core.soft_delete import not_deleted
from app.core.tenant import tenant_filters
from app.models.biz import BizClient, BizClientContact


class ClientRepository(BaseRepository[BizClient]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, BizClient)

    async def get_project_counts(self, tenant_id: UUID, client_ids: list[UUID]) -> dict[UUID, int]:
        """批量获取客户下在制项目数（排除已取消/已关闭）。"""
        if not client_ids:
            return {}
        from app.models.biz import BizProject

        stmt = (
            select(BizProject.client_id, func.count(BizProject.id))
            .where(
                BizProject.tenant_id == tenant_id,
                BizProject.client_id.in_(client_ids),
                BizProject.status.in_(["draft", "active", "on_hold", "delivered"]),
                not_deleted(BizProject),
            )
            .group_by(BizProject.client_id)
        )
        rows = (await self.db.execute(stmt)).all()
        return dict(rows)

    async def get_contacts_for_clients(self, tenant_id: UUID, client_ids: list[UUID]) -> dict[UUID, list[BizClientContact]]:
        if not client_ids:
            return {}
        stmt = (
            select(BizClientContact)
            .where(
                BizClientContact.tenant_id == tenant_id,
                BizClientContact.client_id.in_(client_ids),
                not_deleted(BizClientContact),
            )
            .order_by(BizClientContact.is_primary.desc(), BizClientContact.name.asc())
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        out: dict[UUID, list[BizClientContact]] = {}
        for r in rows:
            out.setdefault(r.client_id, []).append(r)
        return out

    async def get_contacts(self, tenant_id: UUID, client_id: UUID) -> list[BizClientContact]:
        stmt = (
            select(BizClientContact)
            .where(
                BizClientContact.tenant_id == tenant_id,
                BizClientContact.client_id == client_id,
                not_deleted(BizClientContact),
            )
            .order_by(BizClientContact.is_primary.desc(), BizClientContact.name.asc())
        )
        return (await self.db.execute(stmt)).scalars().all()

    async def get_contact(self, contact_id: UUID) -> BizClientContact | None:
        c = await self.db.get(BizClientContact, contact_id)
        if c is None or c.deleted_at is not None:
            return None
        return c
