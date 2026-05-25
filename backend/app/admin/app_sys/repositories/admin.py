from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

"""平台管理员账号仓储。"""

from app.admin.models import PlatformAdmin
from app.core.repository import BaseRepository


class PlatformAdminRepository(BaseRepository[PlatformAdmin]):
    """AdminAuthService 登录与改密使用。"""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, PlatformAdmin)

    async def get_by_username(self, username: str) -> PlatformAdmin | None:
        """按用户名查找活跃管理员。"""
        return await self.get_one(PlatformAdmin.username == username)
