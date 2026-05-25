from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.repository import BaseRepository
from app.core.soft_delete import not_deleted
from app.models.role import Role
from app.models.user import User


class UserRepository(BaseRepository[User]):
    """用户表；登录与 RBAC 预加载 roles。"""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, User)

    _with_roles = [selectinload(User.roles)]

    async def get_with_roles(self, user_id: UUID) -> User | None:
        stmt = (
            select(User)
            .where(User.id == user_id, not_deleted(User))
            .options(*self._with_roles)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        """AuthService.login 按用户名查找（含已删用户需上层再判）。"""
        return await self.get_one(User.username == username)

    async def ensure_username_unique(self, username: str) -> None:
        await self.ensure_unique(User.username, username, message="用户名已存在")

    async def list_with_roles(self, **kwargs):
        return await self.list_page(options=self._with_roles, **kwargs)

    async def load_roles(self, role_ids: list[UUID]) -> list[Role]:
        if not role_ids:
            return []
        result = await self.db.execute(select(Role).where(Role.id.in_(role_ids)))
        return list(result.scalars().all())
