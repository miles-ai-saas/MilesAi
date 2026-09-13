"""Hook Event 契约 v1：请求 envelope 与响应解析。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from miles_common.idgen import generate_uuid
from miles_portal.tenant.hooks.models import HookScope, HookTrigger

SCHEMA_VERSION = "1"

# 各 trigger 允许 modify 合并进 payload 的键
MODIFY_ALLOWLIST: dict[HookTrigger, frozenset[str]] = {
    HookTrigger.BEFORE_CALL: frozenset({"query", "inputs"}),
    HookTrigger.BEFORE_REASONING: frozenset({"query", "query_preview"}),
    HookTrigger.BEFORE_TOOL: frozenset({"params"}),
    HookTrigger.AFTER_CALL: frozenset(),
    HookTrigger.AFTER_REASONING: frozenset(),
    HookTrigger.AFTER_TOOL: frozenset(),
    HookTrigger.ON_ERROR: frozenset(),
}

BEFORE_TRIGGERS = frozenset(
    {
        HookTrigger.BEFORE_CALL,
        HookTrigger.BEFORE_REASONING,
        HookTrigger.BEFORE_TOOL,
    }
)


@dataclass
class ParsedHookResponse:
    """解析后的钩子 HTTP 响应体。"""

    action: str = "continue"  # continue | block | modify
    modify: dict[str, Any] = field(default_factory=dict)  # 允许合并进 payload 的字段
    message: str | None = None  # 阻断或提示文案


def build_event_envelope(
    *,
    tenant_id: UUID,
    trace_id: str | None,
    trigger: HookTrigger,
    scope: HookScope,
    target_id: UUID | None,
    hook_id: UUID,
    hook_name: str,
    payload: dict[str, Any],
    event_id: UUID | None = None,
) -> dict[str, Any]:
    """构建发给钩子的请求 envelope（schema 版本、事件 ID、触发时机与 payload）。"""
    return {
        "schema_version": SCHEMA_VERSION,
        "event_id": str(event_id or generate_uuid()),
        "occurred_at": datetime.now(UTC).isoformat(),
        "tenant_id": str(tenant_id),
        "trace_id": trace_id,
        "trigger": trigger.value,
        "scope": scope.value,
        "target_id": str(target_id) if target_id else None,
        "hook": {"id": str(hook_id), "name": hook_name},
        "payload": payload,
    }


def parse_hook_response(body: Any) -> ParsedHookResponse:
    """解析钩子 HTTP 响应；非 dict、版本不符或 action 非法时退化为默认 continue。"""
    if not isinstance(body, dict):
        return ParsedHookResponse()
    version = body.get("schema_version")
    if version not in (None, SCHEMA_VERSION, 1, "1"):
        return ParsedHookResponse()
    action = str(body.get("action", "continue")).lower()
    if action not in ("continue", "block", "modify"):
        action = "continue"
    modify = body.get("modify")
    if not isinstance(modify, dict):
        modify = {}
    message = body.get("message")
    if message is not None:
        message = str(message)
    return ParsedHookResponse(action=action, modify=modify, message=message)


def apply_modify(payload: dict[str, Any], trigger: HookTrigger, modify: dict[str, Any]) -> dict[str, Any]:
    """按 trigger 白名单合并 modify 字段，避免钩子越权改写 payload 其它键。"""
    allowed = MODIFY_ALLOWLIST.get(trigger, frozenset())
    if not allowed or not modify:
        return payload
    out = dict(payload)
    for key in allowed:
        if key in modify:
            out[key] = modify[key]
    return out
