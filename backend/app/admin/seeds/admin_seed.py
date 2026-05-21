from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password
from app.admin.models import BillingPlan, PlatformAdmin, RateLimitRule


async def seed_admin_ops(session: AsyncSession) -> None:
    settings = get_settings()

    if not await session.scalar(select(BillingPlan.id).limit(1)):
        plans = [
            BillingPlan(
                code="free",
                name="免费版",
                description="试用与小团队",
                price_monthly=Decimal("0"),
                max_knowledge_bases=3,
                max_storage_mb=2048,
                max_tokens_monthly=100_000,
                max_agents=5,
                max_flows=5,
            ),
            BillingPlan(
                code="pro",
                name="专业版",
                description="中型企业",
                price_monthly=Decimal("999"),
                max_knowledge_bases=20,
                max_storage_mb=51200,
                max_tokens_monthly=5_000_000,
                max_agents=50,
                max_flows=50,
            ),
            BillingPlan(
                code="enterprise",
                name="企业版",
                description="大规模部署",
                price_monthly=Decimal("4999"),
                max_knowledge_bases=100,
                max_storage_mb=512000,
                max_tokens_monthly=50_000_000,
                max_agents=500,
                max_flows=500,
            ),
        ]
        for p in plans:
            session.add(p)
        await session.flush()

    if not await session.scalar(select(RateLimitRule.id).limit(1)):
        session.add(
            RateLimitRule(
                name="全局 API 限流",
                path_pattern="/api/v1/*",
                limit_per_minute=300,
                description="默认全局限流",
            )
        )

    username = getattr(settings, "seed_platform_admin_username", "platform")
    existing = await session.scalar(
        select(PlatformAdmin).where(PlatformAdmin.username == username)
    )
    if not existing:
        password = getattr(settings, "seed_platform_admin_password", "admin123")
        session.add(
            PlatformAdmin(
                username=username,
                email="platform@aiengine.local",
                display_name="平台管理员",
                hashed_password=hash_password(password),
                role="super_admin",
            )
        )
        await session.flush()
