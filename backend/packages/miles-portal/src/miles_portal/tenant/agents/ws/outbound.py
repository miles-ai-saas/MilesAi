"""WebSocket 下行：先写入会话环缓（及可选 Redis）再尝试发送。"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from fastapi import WebSocket

from miles_core.logging import get_logger
from miles_portal.tenant.agents.ws.event_buffer import SessionEventBuffer
from miles_portal.tenant.agents.ws.protocol import envelope
from miles_portal.tenant.agents.ws.redis_snapshot import persist_event

logger = get_logger(__name__)

_current_outbound: ContextVar["WsOutbound | None"] = ContextVar("ws_outbound", default=None)


class WsOutbound:
    """绑定一条连接的发送器：缓冲优先，发送失败则标记断开。"""

    def __init__(
        self,
        ws: WebSocket,
        buffer: SessionEventBuffer,
        *,
        session_key: str = "",
    ) -> None:
        self.ws = ws
        self.buffer = buffer
        self.session_key = session_key
        self.alive = True

    async def send(self, event_type: str, payload: dict[str, Any], *, record: bool = True) -> dict[str, Any]:
        """构造事件包；``record=True`` 时写入环缓（及 Redis），再尽力推给当前套接字。"""
        env = envelope(event_type, payload)
        if record:
            self.buffer.append(env)
            await persist_event(self.session_key, env)
        if not self.alive:
            return env
        try:
            await self.ws.send_json(env)
        except Exception:
            self.alive = False
            logger.debug("ws outbound send failed type=%s", event_type, exc_info=True)
        return env

    async def send_recorded(self, env: dict[str, Any]) -> None:
        """重放已落缓的事件包（不再二次写入环缓）。"""
        if not self.alive:
            return
        try:
            await self.ws.send_json(env)
        except Exception:
            self.alive = False
            logger.debug("ws outbound replay failed", exc_info=True)


def set_outbound(outbound: WsOutbound | None):
    """设置当前任务的下行发送器；返回 token 供 ``reset``。"""
    return _current_outbound.set(outbound)


def reset_outbound(token) -> None:  # noqa: ANN001
    """恢复 ContextVar。"""
    _current_outbound.reset(token)


def get_outbound() -> WsOutbound | None:
    """当前连接的下行发送器（无则 None）。"""
    return _current_outbound.get()
