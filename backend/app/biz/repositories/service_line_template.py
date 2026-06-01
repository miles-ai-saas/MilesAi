"""服务线阶段模板仓储。"""

from uuid import UUID

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import BaseRepository
from app.core.soft_delete import not_deleted
from app.models.biz import BizServiceLineTemplate


class ServiceLineTemplateRepository(BaseRepository[BizServiceLineTemplate]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, BizServiceLineTemplate)

    async def get_tenant_template(self, tenant_id: UUID, service_line: str) -> BizServiceLineTemplate | None:
        stmt = (
            select(BizServiceLineTemplate)
            .where(
                BizServiceLineTemplate.service_line == service_line,
                BizServiceLineTemplate.tenant_id == tenant_id,
                not_deleted(BizServiceLineTemplate),
            )
            .limit(1)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_active_template(self, tenant_id: UUID, service_line: str) -> BizServiceLineTemplate | None:
        """优先租户自定义模板，其次全局模板（tenant_id IS NULL）。"""
        stmt = (
            select(BizServiceLineTemplate)
            .where(
                BizServiceLineTemplate.service_line == service_line,
                BizServiceLineTemplate.is_active.is_(True),
                not_deleted(BizServiceLineTemplate),
                (BizServiceLineTemplate.tenant_id == tenant_id) | (BizServiceLineTemplate.tenant_id.is_(None)),
            )
            .order_by(case((BizServiceLineTemplate.tenant_id.is_not(None), 0), else_=1))
            .limit(1)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()
