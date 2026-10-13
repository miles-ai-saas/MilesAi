"""
A2A 协议最小 HTTP Client（JSON-RPC 2.0）。

调用链
------
``tenant.a2a.invoke.execute_a2a_calls`` → ``invoke_a2a_peer``
→ 从 ``A2aPeer.agent_card_json`` 解析 RPC URL → ``message/send``

前置条件
--------
Peer ``status=active`` 且已同步 Agent Card；否则 ``BadRequestError`` 或返回任务预览占位文本。

响应解析
--------
``_extract_text_from_response`` 兼容多种 JSON-RPC result 形状（text/artifacts/parts 等）。

子模块：``auth`` / ``url`` / ``parse`` / ``task`` / ``rpc``；本包为稳定 import 与单测
``monkeypatch.setattr(client_mod, …)`` 门面（含 ``httpx``、``TASK_POLL_*``）。
"""

from __future__ import annotations

import httpx

from miles_portal.tenant.a2a.client.auth import build_auth_headers
from miles_portal.tenant.a2a.client.parse import _extract_text_from_response, _jsonrpc_error
from miles_portal.tenant.a2a.client.rpc import cancel_a2a_peer_task, invoke_a2a_peer
from miles_portal.tenant.a2a.client.task import (
    INTERRUPTED_TASK_STATES,
    STOP_POLLING_TASK_STATES,
    TASK_POLL_INTERVAL_SECONDS,
    TASK_POLL_TIMEOUT_SECONDS,
    TERMINAL_TASK_STATES,
    _looks_like_task,
    _render_agent_task,
    _resolve_agent_task,
    _task_state,
)
from miles_portal.tenant.a2a.client.url import _pick_rpc_url

__all__ = [
    "INTERRUPTED_TASK_STATES",
    "STOP_POLLING_TASK_STATES",
    "TASK_POLL_INTERVAL_SECONDS",
    "TASK_POLL_TIMEOUT_SECONDS",
    "TERMINAL_TASK_STATES",
    "_extract_text_from_response",
    "_jsonrpc_error",
    "_looks_like_task",
    "_pick_rpc_url",
    "_render_agent_task",
    "_resolve_agent_task",
    "_task_state",
    "build_auth_headers",
    "cancel_a2a_peer_task",
    "httpx",
    "invoke_a2a_peer",
]
