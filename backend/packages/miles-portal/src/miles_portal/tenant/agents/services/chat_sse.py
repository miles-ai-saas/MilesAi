"""HTTP 对话 SSE：复用 ``AgentService.chat(..., on_delta=)``，事件类型与 WS 对齐。

帧格式
------
``event: <type>\\ndata: <json>\\n\\n``

- ``chat.delta``：``{"text": "..."}``
- ``chat.step``：步骤对象
- ``tool.confirm_required``：待确认工具
- ``chat.done``：完整 ``ChatResponse`` JSON
- ``chat.error``：``{"message": "...", "code": optional}``
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from miles_common.exceptions import AppError
from miles_core.infra.db import AsyncSessionLocal
from miles_core.logging import get_logger
from miles_core.tenant import TenantContext
from miles_portal.tenant.agents.schemas.agent import ChatRequest
from miles_portal.tenant.agents.services.agent import AgentService
from miles_portal.tenant.agents.ws import protocol as proto

logger = get_logger(__name__)

_DELTA_CHUNK = 32


def format_sse(event: str, payload: dict[str, Any]) -> str:
    """序列化为一条 SSE 帧（含 ``event:`` 行）。"""
    data = json.dumps(payload, ensure_ascii=False)
    return f"event: {event}\ndata: {data}\n\n"


def _chunk_text(text: str, *, size: int = _DELTA_CHUNK) -> list[str]:
    if not text:
        return []
    return [text[i : i + size] for i in range(0, len(text), size)]


async def iter_agent_chat_sse(
    ctx: TenantContext,
    agent_id: UUID,
    body: ChatRequest,
) -> AsyncIterator[str]:
    """跑一轮对话并把 delta/done/error 以 SSE 帧吐出（短会话，与 WS 同口径）。"""
    queue: asyncio.Queue[tuple[str, Any] | None] = asyncio.Queue()
    streamed = False

    async def on_delta(text: str) -> None:
        nonlocal streamed
        if text:
            streamed = True
            await queue.put(("delta", text))

    async def _run() -> None:
        async with AsyncSessionLocal() as db:
            try:
                response = await AgentService(db, ctx).chat(agent_id, body, on_delta=on_delta)
                await db.commit()
                await queue.put(("done", response))
            except AppError as exc:
                await db.rollback()
                await queue.put(("error", {"message": exc.message, "code": exc.status_code}))
            except Exception as exc:
                await db.rollback()
                logger.exception("agent chat sse failed agent_id=%s", agent_id)
                await queue.put(("error", {"message": str(exc)}))
            finally:
                await queue.put(None)

    task = asyncio.create_task(_run())
    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            kind, payload = item
            if kind == "delta":
                yield format_sse(proto.CHAT_DELTA, {"text": payload})
            elif kind == "error":
                yield format_sse(proto.CHAT_ERROR, payload)
            elif kind == "done":
                response = payload
                if response.pending_tool:
                    pt = response.pending_tool
                    yield format_sse(
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
                        yield format_sse(proto.CHAT_STEP, step)
                if not streamed:
                    for chunk in _chunk_text(response.answer or ""):
                        yield format_sse(proto.CHAT_DELTA, {"text": chunk})
                        await asyncio.sleep(0)
                yield format_sse(proto.CHAT_DONE, response.model_dump(mode="json"))
    finally:
        await task
