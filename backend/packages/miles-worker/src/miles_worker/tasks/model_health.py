"""定时探测活跃对话模型可用性，结果写入 ModelConfig.extra。"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from miles_core.infra.db import AsyncSessionLocal, run_worker_db_coro
from miles_core.jobs.tasks import TASK_NAMES
from miles_core.logging import get_logger
from miles_core.models.model import ModelConfig
from miles_core.models.model.catalog import ModelPublishStatus
from miles_core.soft_delete import not_deleted
from miles_integrations.litellm.adapter import CHAT_MODEL_TYPES, litellm_chat_completion
from miles_worker.app import celery_app

logger = get_logger(__name__)

PROBE_MESSAGE = [{"role": "user", "content": "ping"}]


async def _load_models_for_probe() -> list[ModelConfig]:
    """短会话加载待探测模型；退出 with 后连接释放，ORM 实例可作只读快照。"""
    async with AsyncSessionLocal() as db:
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
        models = list((await db.execute(stmt)).scalars().all())
        to_probe: list[ModelConfig] = []
        for model in models:
            if model.tenant_id is None and model.publish_status != ModelPublishStatus.PUBLISHED.value:
                continue
            to_probe.append(model)
        # expire_on_commit=False：expunge 后列属性仍可读，供会话外 litellm 使用。
        for model in to_probe:
            db.expunge(model)
        return to_probe


async def _write_health_extras(updates: list[tuple[UUID, dict]]) -> None:
    """短会话按 id 写回 health_* 到 ModelConfig.extra。"""
    if not updates:
        return
    async with AsyncSessionLocal() as db:
        for model_id, extra in updates:
            row = await db.get(ModelConfig, model_id)
            if row is None:
                continue
            row.extra = extra
        await db.commit()


async def _probe_models_async() -> str:
    checked = 0
    ok_count = 0
    now = datetime.now(UTC).isoformat()

    to_probe = await _load_models_for_probe()

    updates: list[tuple[UUID, dict]] = []
    for model in to_probe:
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
            logger.warning("model health probe failed: %s (%s)", model.name, exc, exc_info=True)
        extra["health_checked_at"] = now
        updates.append((model.id, extra))

    await _write_health_extras(updates)
    return f"checked={checked} ok={ok_count}"


@celery_app.task(name=TASK_NAMES["probe_models_health"])
def probe_models_health() -> str:
    """定时任务：探测活跃对话模型可用性并写回 ``ModelConfig.extra``，返回 ``checked=… ok=…`` 摘要。"""
    try:
        return run_worker_db_coro(_probe_models_async())
    except Exception as exc:
        # 不带堆栈：原样重抛后由 Celery 记录完整堆栈，此处只留可 grep 的上下文。
        logger.error("probe_models_health failed: %s", exc)
        raise
