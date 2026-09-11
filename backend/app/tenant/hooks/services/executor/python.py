"""Python 插件钩子 dispatch。"""

from __future__ import annotations

import asyncio
import importlib
import time
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.tenant.hooks.events import BEFORE_TRIGGERS, apply_modify, build_event_envelope, parse_hook_response
from app.tenant.hooks.models import HookBinding, HookDefinition, HookScope, HookTrigger
from app.common.idgen import generate_uuid

logger = get_logger(__name__)


class HookPythonMixin:
    """执行 Python 插件类型钩子。"""

    db: AsyncSession
    tenant_id: UUID

    async def _run_python(
        self,
        hook: HookDefinition,
        *,
        binding: HookBinding,
        trigger: HookTrigger,
        scope: HookScope,
        target_id: UUID | None,
        payload: dict,
        trace_id: str | None,
    ) -> tuple[dict, dict]:
        cfg = hook.config or {}
        module_path = str(cfg.get("module") or "app.tenant.hooks.plugins.echo")
        func_name = str(cfg.get("function") or "handle")
        event_id = generate_uuid()
        started = time.monotonic()

        if not module_path.startswith("app.tenant.hooks.plugins."):
            await self._write_log(
                hook=hook,
                binding=binding,
                trigger=trigger,
                scope=scope,
                target_id=target_id,
                event_id=event_id,
                trace_id=trace_id,
                status="error",
                duration_ms=0,
                response_action=None,
                error_message="invalid python module path",
            )
            return (
                {"hook": hook.name, "status": "error", "reason": "invalid module"},
                payload,
            )

        envelope = build_event_envelope(
            tenant_id=self.tenant_id,
            trace_id=trace_id,
            trigger=trigger,
            scope=scope,
            target_id=target_id,
            hook_id=hook.id,
            hook_name=hook.name,
            payload=payload,
            event_id=event_id,
        )
        try:
            mod = importlib.import_module(module_path)
            fn = getattr(mod, func_name)
            if asyncio.iscoroutinefunction(fn):
                raw = await fn(envelope)
            else:
                raw = fn(envelope)
            parsed = parse_hook_response(raw if isinstance(raw, dict) else {})
            duration_ms = int((time.monotonic() - started) * 1000)
            current_payload = payload
            if parsed.action == "block" and trigger in BEFORE_TRIGGERS:
                await self._write_log(
                    hook=hook,
                    binding=binding,
                    trigger=trigger,
                    scope=scope,
                    target_id=target_id,
                    event_id=event_id,
                    trace_id=trace_id,
                    status="blocked",
                    duration_ms=duration_ms,
                    response_action="block",
                    error_message=parsed.message,
                )
                return (
                    {
                        "hook": hook.name,
                        "status": "blocked",
                        "message": parsed.message,
                    },
                    current_payload,
                )
            if parsed.action == "modify" and parsed.modify:
                current_payload = apply_modify(current_payload, trigger, parsed.modify)
            await self._write_log(
                hook=hook,
                binding=binding,
                trigger=trigger,
                scope=scope,
                target_id=target_id,
                event_id=event_id,
                trace_id=trace_id,
                status="ok",
                duration_ms=duration_ms,
                response_action=parsed.action,
                error_message=None,
            )
            return (
                {
                    "hook": hook.name,
                    "status": "ok",
                    "action": parsed.action or "continue",
                },
                current_payload,
            )
        except Exception as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            logger.exception("python hook %s failed", hook.name)
            await self._write_log(
                hook=hook,
                binding=binding,
                trigger=trigger,
                scope=scope,
                target_id=target_id,
                event_id=event_id,
                trace_id=trace_id,
                status="error",
                duration_ms=duration_ms,
                response_action=None,
                error_message=str(exc)[:500],
            )
            return (
                {"hook": hook.name, "status": "error", "reason": str(exc)[:200]},
                payload,
            )
