"""钩子执行器：按挂载时机调用 HTTP / Python 扩展（Event v1 envelope）。"""

from __future__ import annotations

from app.core.logging import get_logger
import time
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.trace import get_trace_id
from app.tenant.hooks.events import (
    BEFORE_TRIGGERS,
    ParsedHookResponse,
    apply_modify,
    build_event_envelope,
    parse_hook_response,
)
from app.tenant.hooks.exceptions import HookBlockedError
from app.tenant.hooks.models import (
    HookBinding,
    HookDefinition,
    HookExecutionLog,
    HookScope,
    HookTrigger,
    HookType,
)
from app.tenant.hooks.services.result import HookRunResult
from app.core.soft_delete import not_deleted
from app.utils.idgen import generate_uuid

logger = get_logger(__name__)


class HookExecutor:
    """从 DB 加载绑定并 dispatch HTTP 钩子。"""

    def __init__(self, db: AsyncSession, tenant_id: UUID) -> None:
        self.db = db
        self.tenant_id = tenant_id

    async def run(
        self,
        *,
        trigger: HookTrigger,
        scope: HookScope,
        target_id: UUID | None,
        payload: dict,
    ) -> HookRunResult:
        bindings = await self._load_bindings(trigger, scope, target_id)
        current_payload = dict(payload)
        results: list[dict] = []
        trace_id = get_trace_id()

        for binding, hook in bindings:
            if hook.hook_type == HookType.HTTP:
                item, current_payload = await self._run_http(
                    hook,
                    binding=binding,
                    trigger=trigger,
                    scope=scope,
                    target_id=target_id,
                    payload=current_payload,
                    trace_id=trace_id,
                )
            elif hook.hook_type == HookType.PYTHON:
                item, current_payload = await self._run_python(
                    hook,
                    binding=binding,
                    trigger=trigger,
                    scope=scope,
                    target_id=target_id,
                    payload=current_payload,
                    trace_id=trace_id,
                )
            else:
                logger.warning("unsupported hook type: %s", hook.hook_type)
                item = {
                    "hook": hook.name,
                    "status": "skipped",
                    "reason": "unsupported_type",
                }
                await self._write_log(
                    hook=hook,
                    binding=binding,
                    trigger=trigger,
                    scope=scope,
                    target_id=target_id,
                    event_id=generate_uuid(),
                    trace_id=trace_id,
                    status="skipped",
                    duration_ms=0,
                    response_action=None,
                    error_message="unsupported_type",
                )
            results.append(item)

            if item.get("status") == "blocked":
                raise HookBlockedError(
                    item.get("message") or "请求被钩子拦截",
                    hook_name=hook.name,
                )

        return HookRunResult(results=results, payload=current_payload)

    async def _load_bindings(
        self,
        trigger: HookTrigger,
        scope: HookScope,
        target_id: UUID | None,
    ) -> list[tuple[HookBinding, HookDefinition]]:
        stmt = (
            select(HookBinding)
            .join(HookDefinition, HookBinding.hook_id == HookDefinition.id)
            .where(
                HookBinding.tenant_id == self.tenant_id,
                HookBinding.is_active.is_(True),
                HookDefinition.is_active.is_(True),
                not_deleted(HookBinding),
                not_deleted(HookDefinition),
                HookBinding.trigger == trigger,
            )
            .options(selectinload(HookBinding.hook))
            .order_by(HookBinding.priority.asc())
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        out: list[tuple[HookBinding, HookDefinition]] = []
        for b in rows:
            if b.scope == HookScope.GLOBAL:
                out.append((b, b.hook))
            elif b.scope == scope and (b.target_id is None or b.target_id == target_id):
                out.append((b, b.hook))
        return out

    async def _run_http(
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
        url = cfg.get("url")
        event_id = generate_uuid()
        on_failure = str(cfg.get("on_failure", "ignore")).lower()
        started = time.monotonic()

        if not url:
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
                error_message="missing url",
            )
            return (
                {"hook": hook.name, "status": "error", "reason": "missing url"},
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
        method = str(cfg.get("method", "POST")).upper()
        headers = dict(cfg.get("headers") or {})
        timeout = float(cfg.get("timeout", 5))

        http_status: int | None = None
        response_action: str | None = None
        error_message: str | None = None
        current_payload = payload
        item_status = "ok"

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.request(method, url, json=envelope, headers=headers)
            http_status = resp.status_code
            duration_ms = int((time.monotonic() - started) * 1000)

            if not resp.is_success:
                item_status = "error"
                error_message = f"http_{resp.status_code}"
                await self._write_log(
                    hook=hook,
                    binding=binding,
                    trigger=trigger,
                    scope=scope,
                    target_id=target_id,
                    event_id=event_id,
                    trace_id=trace_id,
                    status=item_status,
                    http_status=http_status,
                    duration_ms=duration_ms,
                    response_action=None,
                    error_message=error_message,
                )
                if on_failure == "fail_request" and trigger in BEFORE_TRIGGERS:
                    raise HookBlockedError(
                        f"钩子 {hook.name} 调用失败（HTTP {resp.status_code}）",
                        hook_name=hook.name,
                    )
                return (
                    {
                        "hook": hook.name,
                        "status": "error",
                        "http_status": resp.status_code,
                    },
                    current_payload,
                )

            parsed = ParsedHookResponse()
            if resp.content:
                try:
                    parsed = parse_hook_response(resp.json())
                except Exception:
                    logger.debug("hook %s response is not JSON", hook.name)

            response_action = parsed.action
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
                    http_status=http_status,
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
                http_status=http_status,
                duration_ms=duration_ms,
                response_action=response_action,
                error_message=None,
            )
            return (
                {
                    "hook": hook.name,
                    "status": "ok",
                    "http_status": http_status,
                    "action": response_action or "continue",
                },
                current_payload,
            )
        except HookBlockedError:
            raise
        except Exception as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            logger.exception("hook %s failed", hook.name)
            error_message = str(exc)[:500]
            await self._write_log(
                hook=hook,
                binding=binding,
                trigger=trigger,
                scope=scope,
                target_id=target_id,
                event_id=event_id,
                trace_id=trace_id,
                status="error",
                http_status=http_status,
                duration_ms=duration_ms,
                response_action=None,
                error_message=error_message,
            )
            if on_failure == "fail_request" and trigger in BEFORE_TRIGGERS:
                raise HookBlockedError(
                    f"钩子 {hook.name} 调用异常",
                    hook_name=hook.name,
                ) from exc
            return (
                {"hook": hook.name, "status": "error", "reason": error_message},
                current_payload,
            )

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
        import asyncio
        import importlib

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

    async def _write_log(
        self,
        *,
        hook: HookDefinition,
        binding: HookBinding,
        trigger: HookTrigger,
        scope: HookScope,
        target_id: UUID | None,
        event_id: UUID,
        trace_id: str | None,
        status: str,
        http_status: int | None,
        duration_ms: int,
        response_action: str | None,
        error_message: str | None,
    ) -> None:
        self.db.add(
            HookExecutionLog(
                tenant_id=self.tenant_id,
                hook_id=hook.id,
                binding_id=binding.id,
                event_id=event_id,
                trace_id=trace_id,
                trigger=trigger.value,
                scope=scope.value,
                target_id=target_id,
                status=status,
                http_status=http_status,
                duration_ms=duration_ms,
                response_action=response_action,
                error_message=error_message,
            )
        )
