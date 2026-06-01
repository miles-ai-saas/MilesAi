from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.repository import BaseRepository
from app.core.soft_delete import not_deleted
from app.models.platform.role import Permission, Role


class RoleRepository(BaseRepository[Role]):
    """角色与 Permission 多对多关联加载。"""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, Role)

    async def get_with_permissions(self, role_id: UUID) -> Role | None:
        stmt = select(Role).where(Role.id == role_id, not_deleted(Role)).options(selectinload(Role.permissions))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def load_permissions(self, permission_ids: list[UUID]) -> list[Permission]:
        if not permission_ids:
            return []
        result = await self.db.execute(select(Permission).where(Permission.id.in_(permission_ids), not_deleted(Permission)))
        return list(result.scalars().all())
