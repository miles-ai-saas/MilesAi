from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.models import PlatformAdmin
from app.core.repository import BaseRepository


class PlatformAdminRepository(BaseRepository[PlatformAdmin]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, PlatformAdmin)

    async def get_by_username(self, username: str) -> PlatformAdmin | None:
        return await self.get_one(PlatformAdmin.username == username)
