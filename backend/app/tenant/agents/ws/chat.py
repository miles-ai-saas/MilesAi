"""智能体对话 WebSocket 端点。"""

from __future__ import annotations

import asyncio
import json
from app.core.logging import get_logger
from uuid import UUID

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.common.exceptions import AppError, UnauthorizedError
from app.core.config import get_settings
from app.core.tenant import TenantContext
from app.infra.db import AsyncSessionLocal
from app.models.generative_job import GenerativeJobStatus
from app.tenant.agents.schemas.agent import ChatMediaIn, ChatRequest, ChatResponse
from app.tenant.agents.services.agent import AgentService
from app.tenant.agents.ws import protocol as proto
from app.tenant.agents.ws.auth import extract_bearer_token, resolve_tenant_context
from app.tenant.agents.ws.job_watch import cancel_generative_job_ws, spawn_job_watchers

logger = get_logger(__name__)

router = APIRouter()


def _pending_job_ids(response: ChatResponse) -> list[UUID]:
    ids: list[UUID] = []
    for row in response.generative_jobs or []:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "")
        if status and status != GenerativeJobStatus.PENDING.value:
            continue
        raw = row.get("id")
        if raw:
            try:
                ids.append(UUID(str(raw)))
            except ValueError:
                continue
    return ids


def _build_chat_request(
    payload: dict,
    *,
    conversation_id: str,
) -> ChatRequest:
    media_raw = payload.get("media") or []
    media: list[ChatMediaIn] = []
    for item in media_raw:
        if isinstance(item, dict) and item.get("attachment_id"):
            media.append(ChatMediaIn.model_validate(item))
    return ChatRequest(
        query=str(payload.get("query") or ""),
        media=media,
        inputs=dict(payload.get("inputs") or {}),
        conversation_id=conversation_id,
        tool_confirmed=bool(payload.get("tool_confirmed")),
        pending_tool_slug=payload.get("pending_tool_slug"),
        pending_tool_params=dict(payload.get("pending_tool_params") or {}),
    )


async def _run_chat_turn(
    ws: WebSocket,
    ctx: TenantContext,
    agent_id: UUID,
    body: ChatRequest,
    job_tasks: set[asyncio.Task],
) -> None:
    async with AsyncSessionLocal() as db:
        try:
            response = await AgentService(db, ctx).chat(agent_id, body)
            await db.commit()
        except AppError as exc:
            await db.rollback()
            await proto.send_json(
                ws,
                proto.CHAT_ERROR,
                {"message": exc.message, "code": exc.status_code},
            )
            return
        except Exception as exc:
            await db.rollback()
            logger.exception("agent chat ws failed agent_id=%s", agent_id)
            await proto.send_json(ws, proto.CHAT_ERROR, {"message": str(exc)})
            return

    if response.pending_tool:
        pt = response.pending_tool
        await proto.send_json(
            ws,
            proto.TOOL_CONFIRM_REQUIRED,
            {
                "slug": pt.slug,
                "name": pt.name,
                "description": pt.description,
                "params": pt.params,
            },
        )

    for step in response.steps or []:
        if isinstance(step, dict):
            await proto.send_json(ws, proto.CHAT_STEP, step)

    await proto.emit_answer_deltas(ws, response.answer)

    done_payload = response.model_dump(mode="json")
    await proto.send_json(ws, proto.CHAT_DONE, done_payload)

    spawn_job_watchers(ws, ctx, _pending_job_ids(response), job_tasks)


@router.websocket("/{agent_id}/chat/ws")
async def agent_chat_websocket(
    websocket: WebSocket,
    agent_id: UUID,
    conversation_id: str = Query(..., min_length=1, max_length=128),
):
    """工作台对话 WebSocket：chat.send / tool.confirm / generative_job.cancel。"""
    if not get_settings().agent_chat_websocket_enabled:
        await websocket.close(code=4403, reason="WebSocket disabled")
        return

    token = extract_bearer_token(websocket)
    if not token:
        await websocket.close(code=4401, reason="Missing token")
        return

    async with AsyncSessionLocal() as db:
        try:
            ctx = await resolve_tenant_context(db, token)
            ctx.require_permission("agent:read")
        except UnauthorizedError:
            await websocket.close(code=4401, reason="Unauthorized")
            return
        except Exception:
            logger.exception("ws auth failed")
            await websocket.close(code=4500, reason="Auth error")
            return

    await websocket.accept()
    job_tasks: set[asyncio.Task] = set()

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                event_type, payload = proto.parse_client_frame(raw)
            except (ValueError, json.JSONDecodeError) as exc:
                await proto.send_json(websocket, proto.CHAT_ERROR, {"message": str(exc)})
                continue

            if event_type == proto.PING:
                await proto.send_json(websocket, proto.PONG, {})
                continue

            if event_type == proto.GENERATIVE_JOB_CANCEL:
                raw_id = payload.get("job_id")
                if not raw_id:
                    await proto.send_json(websocket, proto.CHAT_ERROR, {"message": "缺少 job_id"})
                    continue
                try:
                    job_id = UUID(str(raw_id))
                except ValueError:
                    await proto.send_json(websocket, proto.CHAT_ERROR, {"message": "无效 job_id"})
                    continue
                async with AsyncSessionLocal() as db:
                    try:
                        out = await cancel_generative_job_ws(db, ctx, job_id)
                        await db.commit()
                        await proto.send_json(
                            websocket,
                            proto.GENERATIVE_JOB_PROGRESS,
                            out.model_dump(mode="json"),
                        )
                    except Exception as exc:
                        await db.rollback()
                        await proto.send_json(websocket, proto.CHAT_ERROR, {"message": str(exc)})
                continue

            if event_type == proto.TOOL_CONFIRM:
                payload = {
                    **payload,
                    "query": payload.get("query") or "确认执行工具",
                    "tool_confirmed": True,
                }
                event_type = proto.CHAT_SEND

            if event_type != proto.CHAT_SEND:
                await proto.send_json(
                    websocket,
                    proto.CHAT_ERROR,
                    {"message": f"未知 type: {event_type}"},
                )
                continue

            try:
                body = _build_chat_request(payload, conversation_id=conversation_id)
            except ValidationError as exc:
                err = exc.errors()[0] if exc.errors() else {"msg": "校验失败"}
                await proto.send_json(websocket, proto.CHAT_ERROR, {"message": err.get("msg")})
                continue

            await _run_chat_turn(websocket, ctx, agent_id, body, job_tasks)

    except WebSocketDisconnect:
        pass
    finally:
        for task in list(job_tasks):
            task.cancel()
        await asyncio.gather(*job_tasks, return_exceptions=True)
