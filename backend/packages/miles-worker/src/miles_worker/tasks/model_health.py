"""定时探测活跃对话模型可用性，结果写入 ModelConfig.extra。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from miles_core.logging import get_logger
from miles_core.soft_delete import not_deleted
from miles_core.infra.db import get_worker_session
from miles_ai.integrations.litellm.adapter import CHAT_MODEL_TYPES, litellm_chat_completion
from miles_core.models.model import ModelConfig
from miles_core.models.model.catalog import ModelPublishStatus
from miles_worker.app import celery_app

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


@celery_app.task(name="miles_worker.tasks.model_health.probe_models_health")
def probe_models_health() -> str:
    """定时任务：探测活跃对话模型可用性并写回 ``ModelConfig.extra``，返回 ``checked=… ok=…`` 摘要。"""
    try:
        return asyncio.run(_probe_models_async())
    except Exception:
        logger.exception("probe_models_health failed")
        raise
