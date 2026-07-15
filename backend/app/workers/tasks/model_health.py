"""定时探测活跃对话模型可用性，结果写入 ModelConfig.extra。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.logging import get_logger
from app.core.soft_delete import not_deleted
from app.infra.db import get_worker_session
from app.integrations.litellm.adapter import CHAT_MODEL_TYPES, litellm_chat_completion
from app.models.model import ModelConfig
from app.models.model.catalog import ModelPublishStatus
from app.workers.app import celery_app

logger = get_logger(__name__)

PROBE_MESSAGE = [{"role": "user", "content": "ping"}]


async def _probe_models_async() -> str:
    checked = 0
    ok_count = 0
    now = datetime.now(timezone.utc).isoformat()
    async with get_worker_session() as db:
        stmt = (
            select(ModelConfig)
            .where(
                not_deleted(ModelConfig),
                ModelConfig.is_active.is_(True),
                ModelConfig.model_type.in_(tuple(CHAT_MODEL_TYPES)),
            )
            .order_by(ModelConfig.sort_order.desc(), ModelConfig.created_at.desc())
            .limit(30)
        )
        models = (await db.execute(stmt)).scalars().all()
        for model in models:
            if model.tenant_id is None and model.publish_status != ModelPublishStatus.PUBLISHED.value:
                continue
            checked += 1
            extra = dict(model.extra or {})
            try:
                await litellm_chat_completion(
                    model,
                    PROBE_MESSAGE,
                    temperature=0,
                    max_tokens=8,
                    timeout=20,
                )
                extra["health_status"] = "ok"
                extra["health_message"] = None
                ok_count += 1
            except Exception as exc:
                extra["health_status"] = "down"
                extra["health_message"] = str(exc)[:500]
                logger.warning("model health probe failed: %s (%s)", model.name, exc)
            extra["health_checked_at"] = now
            model.extra = extra
        if checked:
            await db.commit()
    return f"checked={checked} ok={ok_count}"


@celery_app.task(name="app.workers.tasks.model_health.probe_models_health")
def probe_models_health() -> str:
    try:
        return asyncio.run(_probe_models_async())
    except Exception:
        logger.exception("probe_models_health failed")
        raise
