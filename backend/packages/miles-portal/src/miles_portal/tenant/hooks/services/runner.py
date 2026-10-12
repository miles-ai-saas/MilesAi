"""运行时钩子门面：在智能体/流程等执行路径挂载切面。"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from miles_portal.tenant.hooks.models import HookScope, HookTrigger
from miles_portal.tenant.hooks.services.executor import HookExecutor
from miles_portal.tenant.hooks.services.result import HookRunResult

#: ``run_resource`` 的外层时机：before/error 先 APP 后资源；after 先资源后 APP。
AppWrapPhase = Literal["before", "after", "error"]


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

    async def run_resource(
        self,
        trigger: HookTrigger,
        resource_scope: HookScope,
        resource_id: UUID,
        payload: dict,
        *,
        app_id: UUID | None = None,
        phase: AppWrapPhase = "before",
    ) -> HookRunResult:
        """资源级（``AGENT`` / ``FLOW``）钩子；市场安装资源可外包 ``APP``。

        - ``before`` / ``error``：``APP`` → 资源（资源 run 仍含 ``GLOBAL``）
        - ``after``：资源 → ``APP``
        """
        results: list[dict] = []
        current = dict(payload)

        async def _one(scope: HookScope, target: UUID | None) -> None:
            nonlocal current
            out = await self.run(trigger, scope, target, current)
            results.extend(out.results)
            current = out.payload

        if app_id is not None and phase in ("before", "error"):
            await _one(HookScope.APP, app_id)
        await _one(resource_scope, resource_id)
        if app_id is not None and phase == "after":
            await _one(HookScope.APP, app_id)
        return HookRunResult(results=results, payload=current)
