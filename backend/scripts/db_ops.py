"""数据库迁移与种子（供 cli.py 与 scripts/*.py 共用）。"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from sqlalchemy.ext.asyncio import AsyncSession

from scripts.seed import seed_all
from scripts.seed.admin_ops import seed_admin_ops
from scripts.seed.categories import seed_categories, seed_platform_categories
from scripts.seed.compliance import seed_compliance
from scripts.seed.marketplace import seed_marketplace
from scripts.seed.model_catalog import seed_model_catalog
from scripts.seed.tenant import seed_tenant

SeedFn = Callable[[AsyncSession], Awaitable[None]]

SEED_TARGETS: dict[str, SeedFn] = {
    "tenant": seed_tenant,
    "categories": seed_categories,
    "categories-platform": seed_platform_categories,
    "compliance": seed_compliance,
    "marketplace": seed_marketplace,
    "admin": seed_admin_ops,
    "model-catalog": seed_model_catalog,
}


def run_migrate() -> None:
    """子进程执行 alembic upgrade head（与 API lifespan 相同）。"""
    from app.apps.migrate import run_migrations

    print(">>> alembic upgrade head")
    run_migrations()


async def run_seed(target: str = "all") -> None:
    from app.infra.db import AsyncSessionLocal

    if target == "all":
        print(">>> seed all")
        async with AsyncSessionLocal() as session:
            await seed_all(session)
            await session.commit()
        print(">>> seed done")
        return

    fn = SEED_TARGETS.get(target)
    if fn is None:
        raise ValueError(f"unknown seed target: {target}")

    print(f">>> seed {target}")
    async with AsyncSessionLocal() as session:
        await fn(session)
        await session.commit()
    print(">>> seed done")


async def run_init_db(*, migrate: bool, seed: bool) -> None:
    """本地/CI 初始化：先迁移再 seed_all。"""
    if migrate:
        run_migrate()
    if seed:
        await run_seed("all")
    if not migrate and not seed:
        print("nothing to do")


def run_init_db_sync(*, migrate: bool, seed: bool) -> None:
    asyncio.run(run_init_db(migrate=migrate, seed=seed))


def run_seed_sync(target: str) -> None:
    asyncio.run(run_seed(target))
