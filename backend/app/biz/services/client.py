"""客户 CRUD 服务。

客户是业务实体的核心锚点——商机、项目、合同均关联到客户。
支持关键词搜索、保密等级分类、联系人子资源管理。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.repositories.client import ClientRepository
from app.biz.schemas.client import (
    BizClientContactCreate,
    BizClientContactOut,
    BizClientCreate,
    BizClientOut,
    BizClientUpdate,
)
from app.common.exceptions import NotFoundError
from app.common.pagination import paginate
from app.common.schema import PageResult
from app.core.service import BaseService
from app.core.soft_delete import is_marked_deleted, mark_deleted, not_deleted
from app.core.tenant import TenantContext, assert_tenant_access, tenant_filters
from app.models.biz import BizClient, BizClientContact


class ClientService(BaseService):
    """客户与联系人管理——客户列表批量加载关联数据和项目计数。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.repo = ClientRepository(db)

    async def list_clients(
        self,
        *,
        page: int = 1,
        size: int = 20,
        search: str | None = None,
    ) -> PageResult[BizClientOut]:
        """分页查询客户列表，支持名称模糊搜索，批量加载项目计数和联系人。"""
        filters = tenant_filters(self.ctx, BizClient.tenant_id)
        if search:
            filters.append(BizClient.name.ilike(f"%{search}%"))
        result = await paginate(
            self.db,
            BizClient,
            page=page,
            size=size,
            filters=filters,
            order_by=BizClient.name.asc(),
        )

        client_ids = [r.id for r in result.items]
        project_counts = await self.repo.get_project_counts(self.ctx.tenant_id, client_ids)
        contacts_map = await self.repo.get_contacts_for_clients(self.ctx.tenant_id, client_ids)

        return PageResult(
            items=[
                BizClientOut(
                    id=r.id,
                    name=r.name,
                    short_name=r.short_name,
                    industry=r.industry,
                    confidentiality_level=r.confidentiality_level,
                    address=r.address,
                    remark=r.remark,
                    project_count=project_counts.get(r.id, 0),
                    contacts=[BizClientContactOut(id=c.id, client_id=c.client_id, name=c.name, title=c.title, phone=c.phone, email=c.email, is_primary=c.is_primary) for c in contacts_map.get(r.id, [])],
                )
                for r in result.items
            ],
            total=result.total,
            page=result.page,
            size=result.size,
        )

    async def get_client(self, client_id: UUID) -> BizClientOut:
        """获取单个客户详情，含项目计数和联系人列表。"""
        row = await self._get_or_raise(client_id)
        project_counts = await self.repo.get_project_counts(self.ctx.tenant_id, [client_id])
        contacts = await self.repo.get_contacts(self.ctx.tenant_id, client_id)
        return BizClientOut(
            id=row.id,
            name=row.name,
            short_name=row.short_name,
            industry=row.industry,
            confidentiality_level=row.confidentiality_level,
            address=row.address,
            remark=row.remark,
            project_count=project_counts.get(client_id, 0),
            contacts=[BizClientContactOut(id=c.id, client_id=c.client_id, name=c.name, title=c.title, phone=c.phone, email=c.email, is_primary=c.is_primary) for c in contacts],
        )

    async def create_client(self, body: BizClientCreate) -> BizClientOut:
        """创建客户，记录创建人，默认保密等级为 normal。"""
        row = BizClient(
            tenant_id=self.ctx.tenant_id,
            name=body.name.strip(),
            short_name=body.short_name.strip() if body.short_name else None,
            industry=body.industry,
            confidentiality_level=body.confidentiality_level,
            address=body.address,
            remark=body.remark,
            created_by=self.ctx.user_id,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return BizClientOut(
            id=row.id,
            name=row.name,
            short_name=row.short_name,
            industry=row.industry,
            confidentiality_level=row.confidentiality_level,
            address=row.address,
            remark=row.remark,
            project_count=0,
            contacts=[],
        )

    async def update_client(self, client_id: UUID, body: BizClientUpdate) -> BizClientOut:
        """部分更新客户信息（仅更新传入的非空字段）。"""
        row = await self._get_or_raise(client_id)
        for field in ("name", "short_name", "industry", "confidentiality_level", "address", "remark"):
            val = getattr(body, field, None)
            if val is not None:
                setattr(row, field, val.strip() if isinstance(val, str) and field != "industry" and field != "confidentiality_level" else val)
        await self.db.flush()
        return await self.get_client(client_id)

    async def delete_client(self, client_id: UUID) -> None:
        """软删除客户，不影响关联的项目和商机。"""
        row = await self._get_or_raise(client_id)
        await mark_deleted(self.db, row)

    # ── contacts ──

    async def list_contacts(self, client_id: UUID) -> list[BizClientContactOut]:
        """列出指定客户的所有联系人。"""
        await self._get_or_raise(client_id)
        contacts = await self.repo.get_contacts(self.ctx.tenant_id, client_id)
        return [BizClientContactOut(id=c.id, client_id=c.client_id, name=c.name, title=c.title, phone=c.phone, email=c.email, is_primary=c.is_primary) for c in contacts]

    async def create_contact(self, client_id: UUID, body: BizClientContactCreate) -> BizClientContactOut:
        """为客户添加联系人。"""
        await self._get_or_raise(client_id)
        c = BizClientContact(
            tenant_id=self.ctx.tenant_id,
            client_id=client_id,
            name=body.name.strip(),
            title=body.title,
            phone=body.phone,
            email=body.email,
            is_primary=body.is_primary,
        )
        self.db.add(c)
        await self.db.flush()
        await self.db.refresh(c)
        return BizClientContactOut(id=c.id, client_id=c.client_id, name=c.name, title=c.title, phone=c.phone, email=c.email, is_primary=c.is_primary)

    async def update_contact(self, contact_id: UUID, body: BizClientContactCreate) -> BizClientContactOut:
        """编辑联系人信息（is_primary 全量覆盖）。"""
        c = await self.repo.get_contact(contact_id)
        if not c:
            raise NotFoundError("联系人不存在")
        assert_tenant_access(self.ctx, c.tenant_id)
        for field in ("name", "title", "phone", "email"):
            val = getattr(body, field, None)
            if val is not None:
                setattr(c, field, val.strip() if isinstance(val, str) else val)
        c.is_primary = body.is_primary
        await self.db.flush()
        await self.db.refresh(c)
        return BizClientContactOut(id=c.id, client_id=c.client_id, name=c.name, title=c.title, phone=c.phone, email=c.email, is_primary=c.is_primary)

    async def delete_contact(self, contact_id: UUID) -> None:
        """软删除联系人。"""
        c = await self.repo.get_contact(contact_id)
        if not c:
            raise NotFoundError("联系人不存在")
        assert_tenant_access(self.ctx, c.tenant_id)
        await mark_deleted(self.db, c)

    # ── internal ──

    async def _get_or_raise(self, client_id: UUID) -> BizClient:
        row = await self.repo.get_by_id(client_id)
        if not row:
            raise NotFoundError("客户不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        return row
