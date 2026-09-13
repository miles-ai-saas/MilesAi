"""HTTP 钩子 dispatch。"""

from __future__ import annotations

import time
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.idgen import generate_uuid
from miles_core.logging import get_logger
from miles_portal.tenant.hooks.events import (
    BEFORE_TRIGGERS,
    ParsedHookResponse,
    apply_modify,
    build_event_envelope,
    parse_hook_response,
)
from miles_portal.tenant.hooks.exceptions import HookBlockedError
from miles_portal.tenant.hooks.models import HookBinding, HookDefinition, HookScope, HookTrigger

logger = get_logger(__name__)


class HookHttpMixin:
    """执行 HTTP 类型钩子。"""

    db: AsyncSession
    tenant_id: UUID

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
        include_body: bool = False,
    ) -> tuple[dict, dict]:
        """执行 HTTP 钩子。

        ``include_body=True`` 时在结果项附带截断后的响应体（供 Agent 手动触发时读取
        外部系统返回；生命周期钩子保持默认 False，避免结果膨胀）。
        """
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
                item = {
                    "hook": hook.name,
                    "status": "error",
                    "http_status": resp.status_code,
                }
                if include_body:
                    item["body"] = resp.text[:4000]
                return (item, current_payload)

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
                    **({"body": resp.text[:4000]} if include_body else {}),
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
