"""对话 WebSocket 帧协议（与 realtime-transport-design.md 对齐）。"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket

# 客户端 → 服务端
CHAT_SEND = "chat.send"
TOOL_CONFIRM = "tool.confirm"
GENERATIVE_JOB_CANCEL = "generative_job.cancel"
PING = "ping"

# 服务端 → 客户端
CHAT_DELTA = "chat.delta"
CHAT_STEP = "chat.step"
TOOL_CONFIRM_REQUIRED = "tool.confirm_required"
GENERATIVE_JOB_QUEUED = "generative_job.queued"
GENERATIVE_JOB_PROGRESS = "generative_job.progress"
GENERATIVE_JOB_DONE = "generative_job.done"
CHAT_DONE = "chat.done"
CHAT_ERROR = "chat.error"
PONG = "pong"


def utc_now_iso() -> str:
    """返回秒级精度的 UTC ISO8601 时间戳（``Z`` 结尾）。"""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def envelope(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """构造统一事件包：``type`` / ``id`` / ``ts`` / ``payload``。"""
    return {
        "type": event_type,
        "id": str(uuid.uuid4()),
        "ts": utc_now_iso(),
        "payload": payload,
    }


async def send_json(ws: WebSocket, event_type: str, payload: dict[str, Any]) -> None:
    """按统一事件包格式向 WebSocket 发送一次 JSON。"""
    await ws.send_json(envelope(event_type, payload))


async def emit_answer_deltas(ws: WebSocket, text: str, *, chunk_size: int = 32) -> None:
    """将完整回答切分为 chat.delta（各路径共用，后续可换真实流式）。"""
    if not text:
        return
    for i in range(0, len(text), chunk_size):
        chunk = text[i : i + chunk_size]
        await send_json(ws, CHAT_DELTA, {"text": chunk})
        await asyncio.sleep(0)


def parse_client_frame(raw: str) -> tuple[str, dict[str, Any]]:
    """解析客户端帧为 ``(type, payload)``；结构非法时抛 ``ValueError``。"""
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("帧须为 JSON 对象")
    event_type = data.get("type")
    if not isinstance(event_type, str) or not event_type.strip():
        raise ValueError("缺少 type")
    payload = data.get("payload")
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValueError("payload 须为对象")
    return event_type.strip(), payload
