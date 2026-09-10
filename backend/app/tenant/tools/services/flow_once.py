"""``run_flow_once`` 内置工具实现：由 Agent 触发一次**已发布**流程（L1）。

护栏
----
- **仅已发布**：只允许 ``FlowStatus.PUBLISHED`` 且 ``current_version > 0`` 的流程，
  草稿流程不可被 Agent 触发。
- **仅本租户**：经 ``FlowRepository`` + ``assert_tenant_access`` 校验。
- **递归防护**：``ContextVar`` 计数嵌套触发，超过 ``MAX_FLOW_ONCE_DEPTH`` 直接拒绝，
  避免流程内 ``PlatformTool`` 再次 ``run_flow_once`` 造成无限递归。
- **超时**：``asyncio.wait_for`` 限制总时长，默认 120s、上限 300s。

执行复用 ``FlowService.run``（与工作台调试同一链路）：合规扫描、FLOW 级 Hook、
``RunContext`` 装配与 ``tool_invocation_logs`` 审计保持一致。确认策略由
``BUILTIN_REGISTRY``（``require_confirmation=True``）在 ``invoke_tool_with_context`` 把关。
"""

from __future__ import annotations

import asyncio
from contextvars import ContextVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError, NotFoundError
from app.core.soft_delete import is_marked_deleted
from app.core.tenant import TenantContext, assert_tenant_access
from app.models.flow import FlowStatus

MAX_FLOW_ONCE_DEPTH = 2
DEFAULT_TIMEOUT_SEC = 120
MAX_TIMEOUT_SEC = 300

_depth: ContextVar[int] = ContextVar("run_flow_once_depth", default=0)


def _resolve_timeout(raw: object) -> int:
    """解析并夹取超时；非法值回退默认，上限 ``MAX_TIMEOUT_SEC``。"""
    try:
        value = int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT_SEC
    return max(1, min(value, MAX_TIMEOUT_SEC))


def _parse_flow_id(raw: object) -> UUID:
    """解析 flow_id；缺失或非法抛 ``BadRequestError``。"""
    if not raw:
        raise BadRequestError("run_flow_once 需要 flow_id 参数")
    try:
        return UUID(str(raw))
    except (ValueError, TypeError) as exc:
        raise BadRequestError(f"flow_id 非法: {raw}") from exc


async def run_published_flow_once(
    db: AsyncSession,
    ctx: TenantContext,
    *,
    flow_id: object,
    inputs: dict | None = None,
    timeout_sec: object = None,
) -> dict:
    """触发本租户已发布流程一次，返回 ``{flow_id, output, step_count}``。"""
    depth = _depth.get()
    if depth >= MAX_FLOW_ONCE_DEPTH:
        raise BadRequestError(f"流程嵌套触发超过 {MAX_FLOW_ONCE_DEPTH} 层，已拒绝")

    target = _parse_flow_id(flow_id)
    timeout = _resolve_timeout(timeout_sec)
    merged_inputs = dict(inputs or {})

    # 延迟导入：避免 tools ↔ flows 的模块级循环
    from app.tenant.flows.repositories.flow import FlowRepository
    from app.tenant.flows.schemas.flow import FlowRunRequest
    from app.tenant.flows.services.flow import FlowService

    flow = await FlowRepository(db).get_by_id(target)
    if not flow or is_marked_deleted(flow):
        raise NotFoundError("流程不存在")
    assert_tenant_access(ctx, flow.tenant_id)
    if flow.status != FlowStatus.PUBLISHED or flow.current_version <= 0:
        raise BadRequestError("仅可触发已发布流程（草稿流程请先在画布发布）")

    if not str(merged_inputs.get("query") or merged_inputs.get("message") or merged_inputs.get("input") or "").strip():
        raise BadRequestError("run_flow_once 需要 query（或 inputs 中的 query/message/input）")

    token = _depth.set(depth + 1)
    try:
        result = await asyncio.wait_for(
            FlowService(db, ctx).run(target, FlowRunRequest(inputs=merged_inputs)),
            timeout=timeout,
        )
    except asyncio.TimeoutError as exc:
        raise BadRequestError(f"流程执行超时（{timeout}s）") from exc
    finally:
        _depth.reset(token)

    output = result.output
    if not isinstance(output, (str, dict, list)):
        output = str(output)
    return {"flow_id": str(target), "output": output, "step_count": len(result.steps or [])}
