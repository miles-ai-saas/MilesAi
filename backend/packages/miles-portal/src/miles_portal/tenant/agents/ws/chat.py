"""智能体对话 WebSocket 端点。"""

from __future__ import annotations

import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from miles_common.exceptions import AppError, UnauthorizedError
from miles_core.config import get_settings
from miles_core.infra.db import AsyncSessionLocal
from miles_core.logging import get_logger
from miles_core.models.model.generative_job import GenerativeJobStatus
from miles_core.tenant import TenantContext
from miles_portal.tenant.agents.schemas.agent import ChatMediaIn, ChatRequest, ChatResponse
from miles_portal.tenant.agents.services.agent import AgentService
from miles_portal.tenant.agents.ws import protocol as proto
from miles_portal.tenant.agents.ws.auth import extract_bearer_token, resolve_tenant_context
from miles_portal.tenant.agents.ws.job_watch import cancel_generative_job_ws, spawn_job_watchers

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


def _ws_int(payload: dict, field: str, default: int) -> int:
    """取 WS payload 里的整数字段；缺失用 ``default``，非法值抛 ``ValueError``。

    ``payload`` 是客户端直接给的裸 JSON，不要依赖 pydantic 兜底：``int("abc")`` 抛
    ``ValueError``、``int(None)`` 抛 ``TypeError``，都发生在 ``ChatRequest`` 校验之前，
    会绕过调用方的 ``except ValidationError`` 一路穿透 ws 端点。
    """
    raw = payload.get(field, default)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError) as e:
        raise ValueError(f"{field} 须为整数") from e


def _ws_dict(payload: dict, field: str) -> dict:
    """取 WS payload 里的对象字段；缺失/为空用 ``{}``，非对象抛 ``ValueError``。

    直接 ``dict("abc")`` 会抛 ``ValueError: dictionary update sequence element ...``，
    这种报错对客户端毫无意义，故先做类型判定。
    """
    raw = payload.get(field)
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{field} 须为对象")
    return dict(raw)


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
        inputs=_ws_dict(payload, "inputs"),
        conversation_id=conversation_id,
        tool_confirmed=bool(payload.get("tool_confirmed")),
        pending_tool_slug=payload.get("pending_tool_slug"),
        pending_tool_params=_ws_dict(payload, "pending_tool_params"),
        generative_image_n=_ws_int(payload, "generative_image_n", 1),
        generative_video_duration=_ws_int(payload, "generative_video_duration", 5),
    )


async def _run_chat_turn(
    ws: WebSocket,
    ctx: TenantContext,
    agent_id: UUID,
    body: ChatRequest,
    job_tasks: set[asyncio.Task],
) -> None:
    streamed = False

    async def on_delta(text: str) -> None:
        nonlocal streamed
        if text:
            streamed = True
            await proto.send_json(ws, proto.CHAT_DELTA, {"text": text})

    async with AsyncSessionLocal() as db:
        try:
            response = await AgentService(db, ctx).chat(agent_id, body, on_delta=on_delta)
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

    if not streamed:
        await proto.emit_answer_deltas(ws, response.answer)

    done_payload = response.model_dump(mode="json")
    await proto.send_json(ws, proto.CHAT_DONE, done_payload)

    spawn_job_watchers(ws, ctx, _pending_job_ids(response), job_tasks)


async def _authenticate_ws(websocket: WebSocket, token: str) -> TenantContext | None:
    """校验 token 并返回租户上下文；失败按原因关闭连接并返回 None。"""
    async with AsyncSessionLocal() as db:
        try:
            ctx = await resolve_tenant_context(db, token)
            ctx.require_permission("agent:read")
        except UnauthorizedError:
            await websocket.close(code=4401, reason="Unauthorized")
            return None
        except Exception:
            logger.exception("ws auth failed")
            await websocket.close(code=4500, reason="Auth error")
            return None
    return ctx


async def _handle_job_cancel(websocket: WebSocket, ctx: TenantContext, payload: dict) -> None:
    """处理 ``generative_job.cancel``：参数非法或取消失败一律回 ``chat.error``。"""
    raw_id = payload.get("job_id")
    if not raw_id:
        await proto.send_json(websocket, proto.CHAT_ERROR, {"message": "缺少 job_id"})
        return
    try:
        job_id = UUID(str(raw_id))
    except ValueError:
        await proto.send_json(websocket, proto.CHAT_ERROR, {"message": "无效 job_id"})
        return
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


async def _cancel_job_tasks(job_tasks: set[asyncio.Task]) -> None:
    """连接结束时取消本连接派生的 job 监听任务，并等其收尾。"""
    for task in list(job_tasks):
        task.cancel()
    await asyncio.gather(*job_tasks, return_exceptions=True)


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

    ctx = await _authenticate_ws(websocket, token)
    if ctx is None:
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
                await _handle_job_cancel(websocket, ctx, payload)
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
            except ValueError as exc:
                # _ws_int / _ws_dict 抛出的字段级错误，消息已可读
                await proto.send_json(websocket, proto.CHAT_ERROR, {"message": str(exc)})
                continue

            await _run_chat_turn(websocket, ctx, agent_id, body, job_tasks)

    except WebSocketDisconnect:
        pass
    finally:
        await _cancel_job_tasks(job_tasks)
