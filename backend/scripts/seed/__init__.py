"""数据库初始化种子（与 app 业务代码解耦，仅通过 scripts 入口执行）。"""

from scripts.seed.admin_ops import seed_admin_ops
from scripts.seed.categories import seed_categories
from scripts.seed.compliance import seed_compliance
from scripts.seed.marketplace import seed_marketplace
from scripts.seed.prompts import seed_prompts
from scripts.seed.model_catalog import seed_model_catalog
from scripts.seed.tenant import seed_tenant

__all__ = [
    "seed_tenant",
    "seed_categories",
    "seed_compliance",
    "seed_prompts",
    "seed_marketplace",
    "seed_admin_ops",
    "seed_model_catalog",
    "seed_all",
]


async def seed_all(session) -> None:
    """按依赖顺序写入全部种子数据。"""
    await seed_tenant(session)
    await seed_categories(session)
    await seed_compliance(session)
    await seed_prompts(session)
    await seed_marketplace(session)
    await seed_admin_ops(session)
    await seed_model_catalog(session)
