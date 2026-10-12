"""向已登记的 A2A webhook 推送任务状态（best-effort，失败只记日志）。"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import httpx

from miles_core.infra.db import AsyncSessionLocal
from miles_core.logging import get_logger
from miles_core.models.model.generative_job import GenerativeJob
from miles_portal.tenant.a2a.server import (
    build_a2a_task,
    progress_text,
    timestamp_iso,
    to_a2a_task_state,
)
from miles_portal.tenant.a2a.services.server import context_id_from_job_params
from miles_portal.tenant.a2a.services.push_store import list_configs

logger = get_logger(__name__)

_HTTP_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


def _auth_headers(cfg: dict[str, Any]) -> dict[str, str]:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    token = cfg.get("token")
    if token:
        headers["X-A2A-Notification-Token"] = str(token)
    auth = cfg.get("authentication")
    if isinstance(auth, dict):
        schemes = [str(s).lower() for s in (auth.get("schemes") or [])]
        creds = auth.get("credentials")
        if creds and any(s == "bearer" for s in schemes):
            headers["Authorization"] = f"Bearer {creds}"
        elif creds and any(s == "basic" for s in schemes):
            headers["Authorization"] = f"Basic {creds}"
    return headers


async def _post_one(cfg: dict[str, Any], task_payload: dict[str, Any]) -> None:
    url = str(cfg.get("url") or "")
    if not url:
        return
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, follow_redirects=False) as client:
            resp = await client.post(url, json=task_payload, headers=_auth_headers(cfg))
            if resp.status_code >= 400:
                logger.info(
                    "a2a push webhook non-2xx status=%s url=%s",
                    resp.status_code,
                    url[:120],
                )
    except Exception:
        logger.info("a2a push webhook failed url=%s", url[:120], exc_info=True)


async def notify_job_push_configs(tenant_id: UUID | str, job_id: UUID | str) -> None:
    """若该任务登记了 webhook，组装 ``Task`` 并 POST 到各 URL。"""
    try:
        configs = await list_configs(tenant_id=UUID(str(tenant_id)), task_id=UUID(str(job_id)))
    except Exception:
        logger.debug("list push configs failed job=%s", job_id, exc_info=True)
        return
    if not configs:
        return

    async with AsyncSessionLocal() as db:
        job = await db.get(GenerativeJob, UUID(str(job_id)))
        if job is None or str(job.tenant_id) != str(tenant_id):
            return
        agent_id = job.source_ref_id if job.source_ref_type == "agent" else None
        task_payload = build_a2a_task(
            task_id=str(job.id),
            context_id=context_id_from_job_params(job.params) if hasattr(job, "params") else None,
            state=to_a2a_task_state(job.status.value),
            timestamp=timestamp_iso(job.updated_at),
            text=progress_text(progress_message=job.progress_message, percent=job.progress_percent),
            percent=job.progress_percent,
            # 推送不附产物绝对 URL：无请求 base_url；对端可用 tasks/get 取完整 Task
            artifacts=None,
        )
        # 静默：agent_id 仅供日志
        _ = agent_id

    await asyncio.gather(*(_post_one(cfg, task_payload) for cfg in configs))


def schedule_notify_job_push_configs(tenant_id: UUID | str, job_id: UUID | str) -> None:
    """在当前事件循环中调度推送（不阻塞进度发布主路径）。"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(notify_job_push_configs(tenant_id, job_id))
