"""运行时钩子门面：在智能体/流程等执行路径挂载切面。"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from miles_portal.tenant.hooks.models import HookScope, HookTrigger
from miles_portal.tenant.hooks.services.executor import HookExecutor
from miles_portal.tenant.hooks.services.result import HookRunResult


class HookRunner:
    """Agent.chat 等路径使用的钩子门面（如 BEFORE_CALL / AFTER_REASONING）。"""

    def __init__(self, db: AsyncSession, tenant_id: UUID) -> None:
        self._executor = HookExecutor(db, tenant_id)

    async def run(
        self,
        trigger: HookTrigger,
        scope: HookScope,
        target_id: UUID | None,
        payload: dict,
    ) -> HookRunResult:
        """按 trigger/scope 执行已挂载钩子；payload 可能被 before_* 钩子 modify。"""
        return await self._executor.run(
            trigger=trigger,
            scope=scope,
            target_id=target_id,
            payload=payload,
        )
