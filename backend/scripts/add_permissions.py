"""为已有库补充 P3 权限（种子仅在空库时执行）。"""

import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models import Permission, Role
from app.models.role import role_permissions
from app.app_tenant.seeds.seed import DEFAULT_PERMISSIONS


async def main() -> None:
    new_codes = {
        "compliance:read",
        "compliance:write",
        "tools:read",
        "tools:write",
        "marketplace:read",
        "marketplace:write",
        "marketplace:install",
        "marketplace:review",
        "marketplace:rate",
        "task:write",
        "monitor:write",
    }
    async with AsyncSessionLocal() as session:
        for code, name, module in DEFAULT_PERMISSIONS:
            if code not in new_codes:
                continue
            exists = await session.scalar(select(Permission).where(Permission.code == code))
            if exists:
                continue
            perm = Permission(code=code, name=name, module=module)
            session.add(perm)
            await session.flush()
            admin_role = await session.scalar(select(Role).where(Role.code == "super_admin"))
            if admin_role:
                await session.execute(
                    role_permissions.insert().values(role_id=admin_role.id, permission_id=perm.id)
                )
        await session.commit()
    print("permissions updated")


if __name__ == "__main__":
    asyncio.run(main())
