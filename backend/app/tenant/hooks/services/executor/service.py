"""HookExecutor 门面：加载绑定并按优先级串行 dispatch。"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.trace import get_trace_id
from app.core.logging import get_logger
from app.core.soft_delete import not_deleted
from app.tenant.hooks.exceptions import HookBlockedError
from app.tenant.hooks.models import HookBinding, HookDefinition, HookScope, HookTrigger, HookType
from app.tenant.hooks.services.executor.http import HookHttpMixin
from app.tenant.hooks.services.executor.log import HookLogMixin
from app.tenant.hooks.services.executor.python import HookPythonMixin
from app.tenant.hooks.services.result import HookRunResult
from app.utils.idgen import generate_uuid

logger = get_logger(__name__)


class HookExecutor(HookHttpMixin, HookPythonMixin, HookLogMixin):
    """从 DB 加载绑定并 dispatch HTTP / Python 钩子。"""

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
        """按优先级串行 dispatch 命中的绑定；payload 随 modify 钩子逐步演进。

        任一钩子返回 block 时立即抛 ``HookBlockedError``，后续钩子不再执行。
        """
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

    async def run_manual_http(
        self,
        *,
        trigger: HookTrigger,
        scope: HookScope,
        target_id: UUID | None,
        payload: dict,
    ) -> tuple[list[dict], dict]:
        """手动触发已绑定的 **HTTP** 钩子（Agent 工具调用，非生命周期自动挂载）。

        与 ``run`` 的差异：
        - 只执行 HTTP 钩子，跳过 Python 钩子（避免工具调用执行平台插件代码）；
        - ``block`` / ``on_failure=fail_request`` 不抛异常，作为结果项返回，
          由调用方决定如何呈现；
        - 结果项附带截断响应体，便于 Agent 读取外部系统返回。

        返回 ``(results, 合并后的 payload)``。
        """
        pairs = [(binding, hook) for binding, hook in await self._load_bindings(trigger, scope, target_id) if hook.hook_type == HookType.HTTP]
        current_payload = dict(payload)
        results: list[dict] = []
        trace_id = get_trace_id()
        for binding, hook in pairs:
            try:
                item, current_payload = await self._run_http(
                    hook,
                    binding=binding,
                    trigger=trigger,
                    scope=scope,
                    target_id=target_id,
                    payload=current_payload,
                    trace_id=trace_id,
                    include_body=True,
                )
            except HookBlockedError as exc:
                item = {"hook": hook.name, "status": "blocked", "message": str(exc)}
            results.append(item)
        return results, current_payload

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
