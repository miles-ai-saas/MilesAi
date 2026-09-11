"""``invoke_tenant_hook`` 内置工具实现：手动触发已注册的 HTTP 钩子（L1）。

语义
----
与生命周期自动挂载（``HookRunner``）不同，本工具由 Agent 显式调用：按
``trigger`` + ``scope``（+ 可选 ``target_id``）匹配本租户已启用的钩子绑定，
串行执行其中的 **HTTP** 钩子，返回各钩子状态、截断响应体与合并后的 payload。

边界
----
- **仅 HTTP**：Python 钩子（平台插件）不在此执行；
- **仅本租户**：``HookExecutor`` 以 ``ctx.tenant_id`` 过滤绑定；
- **不抛阻断**：``block`` / ``fail_request`` 作为结果项返回（手动调用不应中断对话）；
- **确认**：registry ``require_confirmation=True``，由 ``invoke_tool_with_context`` 把关。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.exceptions import BadRequestError
from miles_core.tenant import TenantContext
from miles_portal.tenant.hooks.models import HookScope, HookTrigger
from miles_portal.tenant.hooks.services.executor import HookExecutor

_HOOK_TYPE_HTTP = "http"


def _parse_enum(raw: object, enum_cls, *, field: str, default=None):
    """解析枚举参数；非法值抛 ``BadRequestError``。"""
    if raw is None or str(raw).strip() == "":
        if default is not None:
            return default
        raise BadRequestError(f"invoke_tenant_hook 需要 {field} 参数")
    try:
        return enum_cls(str(raw).strip())
    except ValueError as exc:
        allowed = "、".join(e.value for e in enum_cls)
        raise BadRequestError(f"{field} 非法（可选：{allowed}）") from exc


def _parse_target_id(raw: object) -> UUID | None:
    """解析可选 target_id；非法值抛 ``BadRequestError``。"""
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return UUID(str(raw).strip())
    except (ValueError, TypeError) as exc:
        raise BadRequestError(f"target_id 非法: {raw}") from exc


async def run_registered_http_hooks(
    db: AsyncSession,
    ctx: TenantContext,
    *,
    trigger: object,
    scope: object = None,
    target_id: object = None,
    payload: dict | None = None,
) -> dict:
    """按 trigger/scope 触发本租户已绑定的 HTTP 钩子，返回执行结果与合并 payload。"""
    hook_trigger = _parse_enum(trigger, HookTrigger, field="trigger")
    hook_scope = _parse_enum(scope, HookScope, field="scope", default=HookScope.GLOBAL)
    target = _parse_target_id(target_id)
    body = payload if isinstance(payload, dict) else {}

    results, merged = await HookExecutor(db, ctx.tenant_id).run_manual_http(
        trigger=hook_trigger,
        scope=hook_scope,
        target_id=target,
        payload=body,
    )
    out: dict = {
        "trigger": hook_trigger.value,
        "scope": hook_scope.value,
        "target_id": str(target) if target else None,
        "count": len(results),
        "results": results,
        "payload": merged,
    }
    if not results:
        out["message"] = "未找到匹配的已启用 HTTP 钩子（请确认 trigger/scope 与绑定状态）"
    return out
