"""角色与权限仓储。"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from miles_core.models.platform.role import Permission, Role
from miles_core.repository import BaseRepository
from miles_core.soft_delete import not_deleted


class RoleRepository(BaseRepository[Role]):
    """角色与 Permission 多对多关联加载。"""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, Role)

    async def get_with_permissions(self, role_id: UUID) -> Role | None:
        """按 ID 加载角色及 permissions；已软删或不存在返回 None。"""
        stmt = select(Role).where(Role.id == role_id, not_deleted(Role)).options(selectinload(Role.permissions))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def load_permissions(self, permission_ids: list[UUID]) -> list[Permission]:
        """按 ID 批量加载未软删权限；忽略不存在的 ID，空输入返回空列表。"""
        if not permission_ids:
            return []
        result = await self.db.execute(select(Permission).where(Permission.id.in_(permission_ids), not_deleted(Permission)))
        return list(result.scalars().all())
