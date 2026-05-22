"""租户默认敏感词。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tenant.compliance.models import SensitiveAction, SensitiveWord
from app.models.tenant import Tenant

DEFAULT_WORDS: list[tuple[str, SensitiveAction, str | None]] = [
    ("违禁品", SensitiveAction.BLOCK, "安全"),
    ("涉密", SensitiveAction.BLOCK, "安全"),
    ("内部资料外传", SensitiveAction.WARN, "合规"),
]


async def seed_compliance_for_tenant(session: AsyncSession, tenant_id) -> None:
    existing = await session.scalar(
        select(SensitiveWord.id).where(SensitiveWord.tenant_id == tenant_id).limit(1)
    )
    if existing:
        return
    for word, action, category in DEFAULT_WORDS:
        session.add(
            SensitiveWord(
                tenant_id=tenant_id,
                word=word,
                category=category,
                action=action,
                is_active=True,
            )
        )
    await session.flush()


async def seed_compliance(session: AsyncSession) -> None:
    tenant_ids = (await session.execute(select(Tenant.id))).scalars().all()
    for tid in tenant_ids:
        await seed_compliance_for_tenant(session, tid)
