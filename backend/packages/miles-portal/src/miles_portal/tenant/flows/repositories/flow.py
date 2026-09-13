"""流程与版本仓储（Flow / FlowVersion）。"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from miles_core.models.flow import Flow, FlowVersion
from miles_core.repository import BaseRepository
from miles_core.soft_delete import not_deleted


class FlowRepository(BaseRepository[Flow]):
    """Flow 主表查询（含版本列表预加载）。"""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, Flow)

    async def get_with_versions(self, flow_id: UUID) -> Flow | None:
        """管理端查看历史版本列表时使用。"""
        stmt = select(Flow).where(Flow.id == flow_id).options(selectinload(Flow.versions))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_version(self, flow_id: UUID, version: int) -> FlowVersion | None:
        """按 flow_id + 版本号取 graph_json 快照。"""
        stmt = select(FlowVersion).where(
            FlowVersion.flow_id == flow_id,
            FlowVersion.version == version,
            not_deleted(FlowVersion),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_versions(self, flow_id: UUID) -> list[FlowVersion]:
        """版本列表，按 version 降序。"""
        stmt = (
            select(FlowVersion)
            .where(
                FlowVersion.flow_id == flow_id,
                not_deleted(FlowVersion),
            )
            .order_by(FlowVersion.version.desc())
        )
        return list((await self.db.execute(stmt)).scalars().all())


class FlowVersionRepository(BaseRepository[FlowVersion]):
    """每次 save_graph 追加的 FlowVersion 行。"""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, FlowVersion)
