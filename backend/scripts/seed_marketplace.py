"""单独写入应用市场官方模板（已有库可执行）。"""

import asyncio

from app.core.database import AsyncSessionLocal
from app.app_tenant.seeds.marketplace_seed import seed_marketplace


async def main() -> None:
    async with AsyncSessionLocal() as session:
        await seed_marketplace(session)
        await session.commit()
    print("marketplace seed done")


if __name__ == "__main__":
    asyncio.run(main())
