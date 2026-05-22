"""运行时钩子门面：在智能体/流程等执行路径挂载切面。"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.tenant.hooks.models import HookScope, HookTrigger
from app.tenant.hooks.services.executor import HookExecutor


class HookRunner:
    def __init__(self, db: AsyncSession, tenant_id: UUID) -> None:
        self._executor = HookExecutor(db, tenant_id)

    async def run(
        self,
        trigger: HookTrigger,
        scope: HookScope,
        target_id: UUID | None,
        payload: dict,
    ) -> list[dict]:
        return await self._executor.run(
            trigger=trigger,
            scope=scope,
            target_id=target_id,
            payload=payload,
        )
