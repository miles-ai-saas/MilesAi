"""数据库初始化种子（与 app 业务代码解耦，仅通过 scripts 入口执行）。"""

from scripts.seed.admin_ops import seed_admin_ops
from scripts.seed.categories import seed_categories
from scripts.seed.compliance import seed_compliance
from scripts.seed.kb_advertising import seed_advertising_kb
from scripts.seed.marketplace import seed_marketplace
from scripts.seed.prompts import seed_prompts
from scripts.seed.model_catalog import seed_model_catalog
from scripts.seed.hooks import seed_hooks
from scripts.seed.skills import seed_skills
from scripts.seed.tools import seed_tools
from scripts.seed.mcp import seed_mcp
from scripts.seed.flows import seed_flows
from scripts.seed.biz import seed_biz_service_line_templates
from scripts.seed.biz_ai import seed_biz_service_line_agents
from scripts.seed.biz_roles import seed_biz_roles
from scripts.seed.tenant import seed_tenant

__all__ = [
    "seed_tenant",
    "seed_biz_service_line_templates",
    "seed_biz_roles",
    "seed_biz_service_line_agents",
    "seed_categories",
    "seed_compliance",
    "seed_prompts",
    "seed_marketplace",
    "seed_admin_ops",
    "seed_model_catalog",
    "seed_tools",
    "seed_mcp",
    "seed_skills",
    "seed_hooks",
    "seed_flows",
    "seed_advertising_kb",
    "seed_all",
]


async def seed_all(session) -> None:
    """按依赖顺序写入全部种子数据。"""
    await seed_tenant(session)
    await seed_biz_service_line_templates(session)
    await seed_biz_roles(session)
    await seed_categories(session)
    await seed_compliance(session)
    await seed_prompts(session)
    await seed_tools(session)
    await seed_mcp(session)
    await seed_skills(session)
    await seed_hooks(session)
    await seed_flows(session)
    await seed_marketplace(session)
    await seed_admin_ops(session)
    await seed_model_catalog(session)
    await seed_advertising_kb(session)
    await seed_biz_service_line_agents(session)
