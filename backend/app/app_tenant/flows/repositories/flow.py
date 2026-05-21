from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.repository import BaseRepository
from app.models.flow import Flow, FlowVersion


class FlowRepository(BaseRepository[Flow]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, Flow)

    async def get_with_versions(self, flow_id: UUID) -> Flow | None:
        stmt = (
            select(Flow)
            .where(Flow.id == flow_id)
            .options(selectinload(Flow.versions))
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_version(self, flow_id: UUID, version: int) -> FlowVersion | None:
        stmt = select(FlowVersion).where(
            FlowVersion.flow_id == flow_id,
            FlowVersion.version == version,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()


class FlowVersionRepository(BaseRepository[FlowVersion]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, FlowVersion)
