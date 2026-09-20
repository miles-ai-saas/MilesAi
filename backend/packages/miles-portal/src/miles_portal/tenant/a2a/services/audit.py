"""A2A 调用审计（落租户流水 ``aud_logs``）。

为什么自开会话：``write_tenant_audit_log`` 的契约是「不 commit，由调用方会话收尾」。
若复用请求作用域的 ``db``，``message/send`` 业务失败回滚会**连带丢掉留痕** —— 而失败
恰恰是最需要留痕的时候。流式请求更甚：请求作用域会话在开流时就已经提交释放了
（见 message-stream 设计的 §3.5），根本没有会话可复用。
"""

from __future__ import annotations

from uuid import UUID

from miles_core.infra.db import AsyncSessionLocal
from miles_core.logging import get_logger
from miles_core.tenant import TenantContext
from miles_portal.tenant.audit_log.services.audit_log import write_tenant_audit_log

logger = get_logger(__name__)


async def write_a2a_audit(
    *,
    ctx: TenantContext,
    agent_id: UUID,
    action: str,
    outcome: str,
    detail: dict | None = None,
) -> None:
    """写一条 A2A 调用流水；失败只记日志，绝不影响业务返回（审计是旁路）。"""
    payload: dict = {"outcome": outcome, "apiKeyId": str(ctx.api_key_id) if ctx.api_key_id else None}
    if detail:
        payload.update(detail)
    try:
        async with AsyncSessionLocal() as db:
            await write_tenant_audit_log(
                db,
                ctx,
                action=action,
                resource_type="agent",
                resource_id=str(agent_id),
                detail=payload,
            )
            await db.commit()
    except Exception:
        logger.exception("A2A 审计写入失败: action=%s agent_id=%s", action, agent_id)
