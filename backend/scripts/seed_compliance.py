"""为已有租户补充默认敏感词（租户尚无敏感词时）。"""

import asyncio

from app.app_tenant.seeds.compliance_seed import seed_compliance
from app.core.database import AsyncSessionLocal


async def main() -> None:
    async with AsyncSessionLocal() as session:
        await seed_compliance(session)
        await session.commit()
    print("compliance seed done")


if __name__ == "__main__":
    asyncio.run(main())
