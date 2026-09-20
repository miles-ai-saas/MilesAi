"""A2A 调用审计（落租户流水 ``aud_logs``）。

为什么自开会话：``write_tenant_audit_log`` 的契约是「不 commit，由调用方会话收尾」。
若复用请求作用域的 ``db``，``message/send`` 业务失败回滚会**连带丢掉留痕** —— 而失败
恰恰是最需要留痕的时候。流式请求更甚：请求作用域会话在开流时就已经提交释放了
（见 message-stream 设计的 §3.5），根本没有会话可复用。
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any
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
    """写一条 A2A 调用流水；失败只记日志，绝不影响业务返回（审计是旁路）。

    ``detail`` 只传元数据（``method`` / ``contextId`` / ``taskId`` / ``durationMs`` /
    ``errorCode`` 等），**不得传消息正文、智能体回复或 token** —— ``aud_logs`` 是租户
    可见面，正文可能含隐私内容。
    """
    payload: dict = {**(detail or {}), "outcome": outcome, "apiKeyId": str(ctx.api_key_id) if ctx.api_key_id else None}
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


#: 脱离取消作用域的审计写入 task 的强引用。
#: 审计必须跑在独立 task 里（理由见 ``services/server.py`` 的 ``_stream_turn``）；不持有强引用
#: 的话，task 可能在落库前被 GC 回收，留痕静默丢失。
_PENDING_AUDITS: set[asyncio.Task] = set()


def schedule_audit(coro: Coroutine[Any, Any, None]) -> None:
    """把一次审计写入交给脱离调用方取消作用域的独立 task。**同步**，不 ``await``。"""
    task = asyncio.create_task(coro)
    _PENDING_AUDITS.add(task)
    task.add_done_callback(_PENDING_AUDITS.discard)


async def drain_pending_audits() -> None:
    """等在飞的审计 task 全部落地（测试断言用）。

    只 gather **未完成**的：``gather`` 对已 done 的 task 不会让出控制权；若集合里只剩
    「已完成但 discard 回调尚未执行」的 task，纯靠 ``while 集合非空 + gather 全集`` 会占满
    事件循环（连外层 ``wait_for`` 超时都触发不了）。未完成列表为空即返回 —— 已完成的会由
    done 回调自行从集合剔除，不必在此强清。
    """
    while True:
        pending = [t for t in _PENDING_AUDITS if not t.done()]
        if not pending:
            return
        await asyncio.gather(*pending, return_exceptions=True)
