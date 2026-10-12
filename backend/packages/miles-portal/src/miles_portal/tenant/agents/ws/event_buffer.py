"""对话 WebSocket 会话事件环缓（单进程内存，供断线续传）。

按 ``tenant:user:agent:conversation`` 隔离；多 worker 不共享，gap 时由客户端
回退本地历史 / HTTP。TTL 到期清空，避免泄漏。
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from miles_core.config import get_settings


@dataclass
class SessionEventBuffer:
    """有界事件环缓。"""

    max_size: int
    events: deque[dict[str, Any]] = field(default_factory=deque)
    updated_at: float = field(default_factory=time.monotonic)

    def append(self, envelope: dict[str, Any]) -> None:
        """追加完整事件包（含 ``id``）。"""
        self.events.append(envelope)
        while len(self.events) > self.max_size:
            self.events.popleft()
        self.updated_at = time.monotonic()

    def events_after(self, last_event_id: str | None) -> tuple[list[dict[str, Any]], bool]:
        """返回 ``(待重放事件, 是否存在缺口)``。

        - 无 ``last_event_id``：不重放，无缺口
        - id 在缓冲中：重放其后事件
        - 缓冲空：无缺口（新会话或已过期）
        - id 不在缓冲且缓冲非空：缺口（客户端需回退本地/HTTP）
        """
        if not last_event_id:
            return [], False
        if not self.events:
            return [], False
        ids = [str(e.get("id") or "") for e in self.events]
        try:
            idx = ids.index(last_event_id)
        except ValueError:
            return [], True
        return list(self.events)[idx + 1 :], False

    @property
    def last_event_id(self) -> str | None:
        if not self.events:
            return None
        return str(self.events[-1].get("id") or "") or None


_buffers: dict[str, SessionEventBuffer] = {}


def session_key(
    *,
    tenant_id: UUID,
    user_id: UUID,
    agent_id: UUID,
    conversation_id: str,
) -> str:
    """会话缓冲键。"""
    cid = (conversation_id or "").strip()[:128] or "default"
    return f"{tenant_id}:{user_id}:{agent_id}:{cid}"


def _purge_expired(now: float, ttl: float) -> None:
    dead = [k for k, buf in _buffers.items() if now - buf.updated_at > ttl]
    for k in dead:
        _buffers.pop(k, None)


def get_session_buffer(key: str) -> SessionEventBuffer:
    """取或创建会话缓冲；顺带清理过期项。"""
    settings = get_settings()
    max_size = max(8, int(settings.agent_chat_ws_event_buffer_size))
    ttl = max(30.0, float(settings.agent_chat_ws_event_buffer_ttl_sec))
    now = time.monotonic()
    _purge_expired(now, ttl)
    buf = _buffers.get(key)
    if buf is None:
        buf = SessionEventBuffer(max_size=max_size)
        _buffers[key] = buf
    else:
        buf.max_size = max_size
        buf.updated_at = now
    return buf


def clear_session_buffers() -> None:
    """测试用：清空全局缓冲。"""
    _buffers.clear()
