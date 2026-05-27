"""记录模型 Token 用量。"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model import ModelConfig
from app.models.model_usage_log import ModelUsageLog


@dataclass(frozen=True)
class UsageRecordContext:
    db: AsyncSession
    tenant_id: UUID
    model: ModelConfig
    source: str = "chat"
    source_id: UUID | None = None


async def record_model_usage(
    ctx: UsageRecordContext,
    *,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> None:
    total = max(0, prompt_tokens) + max(0, completion_tokens)
    if total <= 0:
        return
    row = ModelUsageLog(
        tenant_id=ctx.tenant_id,
        model_config_id=ctx.model.id,
        model_name=ctx.model.name,
        source=ctx.source,
        source_id=ctx.source_id,
        prompt_tokens=max(0, prompt_tokens),
        completion_tokens=max(0, completion_tokens),
        total_tokens=total,
    )
    ctx.db.add(row)
    await ctx.db.flush()
