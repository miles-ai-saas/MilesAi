"""Python 插件钩子 dispatch。"""

from __future__ import annotations

import asyncio
import importlib
import time
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.idgen import generate_uuid
from miles_core.logging import get_logger
from miles_portal.tenant.hooks.events import BEFORE_TRIGGERS, apply_modify, build_event_envelope, parse_hook_response
from miles_portal.tenant.hooks.models import HookBinding, HookDefinition, HookScope, HookTrigger

logger = get_logger(__name__)

# 安全边界：仅允许加载本包内的插件模块，避免租户配置的 config.module 成为任意代码执行入口
_ALLOWED_MODULE_PREFIX = "miles_portal.tenant.hooks.plugins."
_DEFAULT_MODULE = _ALLOWED_MODULE_PREFIX + "echo"
_DEFAULT_FUNCTION = "handle"


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
        """执行 Python 插件钩子。

        插件模块必须位于 ``_ALLOWED_MODULE_PREFIX`` 下，否则直接拒绝（不 import）；
        插件可返回 ``block`` / ``modify`` / ``continue`` 动作，语义与 HTTP 钩子一致，
        但 Python 钩子异常不做 ``fail_request`` 阻断（仅记录并返回 error 项）。
        """
        cfg = hook.config or {}
        module_path = str(cfg.get("module") or _DEFAULT_MODULE)
        func_name = str(cfg.get("function") or _DEFAULT_FUNCTION)
        event_id = generate_uuid()
        started = time.monotonic()

        async def write_log(
            *,
            status: str,
            duration_ms: int,
            response_action: str | None = None,
            error_message: str | None = None,
        ) -> None:
            """写入本次钩子执行的审计日志。

            本次调用的 hook / binding / trigger / scope / target_id / event_id / trace_id
            对所有分支都相同，故在此固化，调用处只传随分支变化的字段。
            """
            await self._write_log(
                hook=hook,
                binding=binding,
                trigger=trigger,
                scope=scope,
                target_id=target_id,
                event_id=event_id,
                trace_id=trace_id,
                status=status,
                duration_ms=duration_ms,
                response_action=response_action,
                error_message=error_message,
            )

        if not module_path.startswith(_ALLOWED_MODULE_PREFIX):
            await write_log(status="error", duration_ms=0, error_message="invalid python module path")
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
            raw = await fn(envelope) if asyncio.iscoroutinefunction(fn) else fn(envelope)
            parsed = parse_hook_response(raw if isinstance(raw, dict) else {})
            duration_ms = int((time.monotonic() - started) * 1000)
            current_payload = payload
            if parsed.action == "block" and trigger in BEFORE_TRIGGERS:
                await write_log(
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
            await write_log(
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
            await write_log(
                status="error",
                duration_ms=duration_ms,
                error_message=str(exc)[:500],
            )
            return (
                {"hook": hook.name, "status": "error", "reason": str(exc)[:200]},
                payload,
            )
