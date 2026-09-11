"""生图/生视频任务完成后，把结果回写到对话消息 artifacts。

异步任务成功时 ChatResponse 往往仍是 pending 占位；若不回写，任务中心有结果、会话里却没有。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import String, cast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from miles_core.models.agent.chat_call import AgentChatCall
from miles_core.models.agent.chat_session import AgentChatMessage, AgentChatSession
from miles_core.models.model.generative_job import GenerativeJob, GenerativeJobStatus

logger = logging.getLogger(__name__)


def artifacts_payload_from_job(job: GenerativeJob) -> list[dict]:
    """把 GenerativeJob 转成 ChatMessage.artifacts 结构。"""
    kind = "image" if job.kind == "image" else "video"
    base: dict = {
        "kind": kind,
        "job_id": str(job.id),
        "progress_percent": job.progress_percent,
        "progress_message": job.progress_message,
        "error_message": job.error_message,
    }
    if job.status == GenerativeJobStatus.PENDING:
        return [{**base, "status": "pending"}]
    if job.status == GenerativeJobStatus.RUNNING:
        return [{**base, "status": "running"}]
    if job.status == GenerativeJobStatus.FAILED:
        return [{**base, "status": "failed"}]
    if job.status == GenerativeJobStatus.CANCELLED:
        return [{**base, "status": "cancelled"}]
    if job.status != GenerativeJobStatus.SUCCESS:
        return [{**base, "status": job.status.value}]

    result = job.result if isinstance(job.result, dict) else {}
    result_kind = str(result.get("kind") or kind)
    mime = result.get("mime_type")
    raw_ids = result.get("attachment_ids")
    ids = [str(i) for i in raw_ids] if isinstance(raw_ids, list) and raw_ids else ([str(result["attachment_id"])] if result.get("attachment_id") else [])
    raw_mids = result.get("media_asset_ids")
    mids = [str(i) for i in raw_mids] if isinstance(raw_mids, list) and raw_mids else ([str(result["media_asset_id"])] if result.get("media_asset_id") else [])
    if not ids:
        return [{**base, "kind": result_kind, "status": "success", "caption": "生成完成"}]
    return [
        {
            **base,
            "kind": result_kind,
            "status": "success",
            "caption": "生成完成",
            "attachment_id": attachment_id,
            "mime_type": mime,
            "media_asset_id": mids[i] if i < len(mids) else (mids[0] if mids else None),
        }
        for i, attachment_id in enumerate(ids)
    ]


def _job_id_in_payload(payload: object, job_id: str) -> bool:
    if payload is None:
        return False
    text = str(payload)
    return job_id in text


def _replace_job_artifacts(existing: list | None, job_id: str, next_arts: list[dict]) -> list[dict]:
    prev = [a for a in (existing or []) if isinstance(a, dict) and str(a.get("job_id") or "") != job_id]
    return [*prev, *next_arts]


async def _resolve_conversation_id(db: AsyncSession, job: GenerativeJob) -> str | None:
    params = job.params if isinstance(job.params, dict) else {}
    raw = params.get("conversation_id") or (params.get("agent_config") or {}).get("_conversation_id")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    if not job.trace_id:
        return None
    call = await db.scalar(
        select(AgentChatCall)
        .where(
            AgentChatCall.tenant_id == job.tenant_id,
            AgentChatCall.trace_id == job.trace_id,
        )
        .order_by(AgentChatCall.created_at.desc())
        .limit(1)
    )
    if call and call.conversation_id:
        return call.conversation_id.strip() or None
    return None


async def sync_job_result_to_chat_messages(db: AsyncSession, job: GenerativeJob) -> int:
    """把任务终态写回引用该 job_id 的对话消息；找不到时尝试按 conversation/trace 补一条助手消息。"""
    if job.status not in {
        GenerativeJobStatus.SUCCESS,
        GenerativeJobStatus.FAILED,
        GenerativeJobStatus.CANCELLED,
    }:
        return 0

    job_id = str(job.id)
    next_arts = artifacts_payload_from_job(job)
    patched = 0

    stmt = (
        select(AgentChatMessage)
        .where(
            AgentChatMessage.tenant_id == job.tenant_id,
            or_(
                cast(AgentChatMessage.artifacts, String).contains(job_id),
                cast(AgentChatMessage.steps, String).contains(job_id),
            ),
        )
        .order_by(AgentChatMessage.created_at.desc())
        .limit(40)
    )
    rows = list((await db.scalars(stmt)).all())
    for row in rows:
        if not _job_id_in_payload(row.artifacts, job_id) and not _job_id_in_payload(row.steps, job_id):
            continue
        row.artifacts = _replace_job_artifacts(row.artifacts if isinstance(row.artifacts, list) else [], job_id, next_arts)
        flag_modified(row, "artifacts")
        patched += 1

    if patched:
        await db.flush()
        logger.info("synced generative job %s into %s chat message(s)", job_id, patched)
        return patched

    # 会话回合丢失时：按 conversation / trace 补一条助手消息，避免「任务有、会话无」
    conversation_id = await _resolve_conversation_id(db, job)
    if not conversation_id or job.status != GenerativeJobStatus.SUCCESS:
        return 0

    session = await db.get(AgentChatSession, conversation_id)
    if not session or session.tenant_id != job.tenant_id:
        return 0

    agent_id = session.agent_id
    params = job.params if isinstance(job.params, dict) else {}
    if params.get("agent_id"):
        try:
            agent_id = UUID(str(params["agent_id"]))
        except (ValueError, TypeError, AttributeError):
            pass
    elif job.source_ref_type == "agent" and job.source_ref_id:
        agent_id = job.source_ref_id

    max_sort = await db.scalar(
        select(AgentChatMessage.sort_index).where(AgentChatMessage.session_id == conversation_id).order_by(AgentChatMessage.sort_index.desc()).limit(1)
    )
    sort_index = int(max_sort or -1) + 1
    prompt = str(params.get("prompt") or "").strip()
    content = "已生成完成" if not prompt else f"已根据「{prompt[:80]}」生成完成"
    db.add(
        AgentChatMessage(
            session_id=conversation_id,
            tenant_id=job.tenant_id,
            agent_id=agent_id,
            role="assistant",
            content=content,
            artifacts=next_arts,
            steps=[{"type": "generative_job", "job_id": job_id, "kind": job.kind, "status": job.status.value}],
            trace_id=job.trace_id,
            sort_index=sort_index,
        )
    )
    session.updated_at = datetime.now(timezone.utc)
    await db.flush()
    logger.info("appended chat message for orphan generative job %s into session %s", job_id, conversation_id)
    return 1


async def hydrate_chat_messages_artifacts(db: AsyncSession, messages: list[AgentChatMessage]) -> bool:
    """读取会话时：把仍为 pending/running 的 artifacts 按真实 job 状态校正并落库。"""
    job_ids: list[UUID] = []
    seen: set[str] = set()
    for msg in messages:
        for art in msg.artifacts or []:
            if not isinstance(art, dict):
                continue
            jid = art.get("job_id")
            if not jid:
                continue
            status = art.get("status")
            if status in ("success", "failed", "cancelled") and (art.get("attachment_id") or art.get("media_asset_id") or status != "success"):
                continue
            if status == "success" and (art.get("attachment_id") or art.get("media_asset_id")):
                continue
            key = str(jid)
            if key in seen:
                continue
            try:
                seen.add(key)
                job_ids.append(UUID(key))
            except (ValueError, TypeError, AttributeError):
                continue

    if not job_ids:
        return False

    jobs = list((await db.scalars(select(GenerativeJob).where(GenerativeJob.id.in_(job_ids)))).all())
    by_id = {str(j.id): j for j in jobs}
    changed = False
    for msg in messages:
        arts = [a for a in (msg.artifacts or []) if isinstance(a, dict)]
        if not arts:
            continue
        next_arts: list[dict] = []
        handled_jobs: set[str] = set()
        msg_changed = False
        for art in arts:
            jid = str(art.get("job_id") or "")
            job = by_id.get(jid) if jid else None
            if not job or job.status in (GenerativeJobStatus.PENDING, GenerativeJobStatus.RUNNING):
                next_arts.append(art)
                continue
            if jid in handled_jobs:
                msg_changed = True
                continue
            handled_jobs.add(jid)
            next_arts.extend(artifacts_payload_from_job(job))
            msg_changed = True
        if msg_changed:
            msg.artifacts = next_arts
            flag_modified(msg, "artifacts")
            changed = True

    if changed:
        await db.flush()
    return changed
