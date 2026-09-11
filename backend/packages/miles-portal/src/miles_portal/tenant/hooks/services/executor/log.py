"""钩子执行审计日志写入。"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from miles_portal.tenant.hooks.models import HookBinding, HookDefinition, HookExecutionLog, HookScope, HookTrigger


class HookLogMixin:
    """写入 ``HookExecutionLog`` 行。"""

    db: AsyncSession
    tenant_id: UUID

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
        http_status: int | None = None,
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
