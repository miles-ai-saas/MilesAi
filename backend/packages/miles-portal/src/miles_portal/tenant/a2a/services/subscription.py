"""A2A ``tasks/resubscribe`` 用例层：把生成任务进度续播为 SSE 帧。

与 ``message/stream``（``services/server.py``）方向相同、来源不同：那边跑一轮对话并把 token
逐片下发，这边**不产生**任何内容，只把平台既有的生成任务进度（Redis Pub/Sub）转成 A2A 帧。
故它复用 ``services/streaming`` 的帧原语、``services/audit`` 的旁路留痕，以及
``generative.services.job_watch`` 的订阅循环。

可续播范围：只认真实生成任务 id（``params.id`` 即 job id）。``message/stream`` 的合成
``taskId`` 不落库，拿它来订阅会按「任务不存在」回 ``-32001``。
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.exceptions import BadRequestError, NotFoundError
from miles_core.infra.db import AsyncSessionLocal
from miles_core.logging import get_logger
from miles_core.models.model.generative_job import GenerativeJob
from miles_core.tenant import TenantContext
from miles_portal.tenant.a2a.server import (
    AUDIT_ACTION_TASKS_RESUBSCRIBE,
    AUDIT_OUTCOME_CANCELED,
    AUDIT_OUTCOME_FAILED,
    AUDIT_OUTCOME_OK,
    INVALID_PARAMS,
    INVALID_REQUEST,
    TASK_NOT_FOUND,
    TASK_STATE_CANCELED,
    TASK_STATE_COMPLETED,
    TASK_STATE_FAILED,
    TASK_STATE_UNKNOWN,
    build_a2a_artifact_update,
    build_a2a_artifacts,
    build_a2a_status_update,
    build_a2a_task,
    is_terminal_generative_status,
    jsonrpc_error,
    jsonrpc_result,
    now_iso,
    progress_text,
    to_a2a_task_state,
)
from miles_portal.tenant.a2a.services import streaming
from miles_portal.tenant.a2a.services.audit import schedule_audit, write_a2a_audit
from miles_portal.tenant.a2a.services.server import (
    context_id_from_job_params,
    load_owned_agent_task,
    load_published_agent,
    parse_task_id,
)
from miles_portal.tenant.generative.services.job_execution import get_generative_job_for_tenant
from miles_portal.tenant.generative.services.job_watch import watch_generative_job

logger = get_logger(__name__)

#: 订阅流的轮询间隔（秒）：``get_message`` 的阻塞上限、DB 降级路径的刷新间隔、空闲刻度间隔。
#: Pub/Sub 有消息时立即返回、不受它影响，故它实际决定的是**保活节奏**与降级路径的取数频率。
SUBSCRIPTION_POLL_SECONDS = 2.0

#: 订阅的安全上限（秒）。规范要求流在 interrupted/terminal 状态结束，到点仍在跑就是**有意偏离**：
#: 病态任务不该无限占住连接。对端可据此再订阅一次（见 docs/guides/a2a.md）。
SUBSCRIPTION_MAX_SECONDS = 1800.0

#: 终态 → 审计 outcome。``canceled`` 记 ``ok``：任务被取消是合法终态、订阅正常走完；
#: ``canceled`` 这一 outcome 本设计里专指「对端断连」，混用会让两者不可区分。
_TERMINAL_OUTCOME = {
    TASK_STATE_COMPLETED: AUDIT_OUTCOME_OK,
    TASK_STATE_CANCELED: AUDIT_OUTCOME_OK,
    TASK_STATE_FAILED: AUDIT_OUTCOME_FAILED,
}


def _progress_fingerprint(job: GenerativeJob) -> tuple[str, object, object]:
    """进度指纹（A2A 状态 + 进度文字 + 百分比）：三者全同即「对端没有新信息」。"""
    return (to_a2a_task_state(str(job.status.value)), job.progress_message, job.progress_percent)


async def open_task_subscription(
    db: AsyncSession,
    ctx: TenantContext,
    agent_id: UUID,
    payload: object,
    *,
    base_url: str,
) -> dict | AsyncIterator[str]:
    """``tasks/resubscribe`` 入口：前置校验失败回 JSON-RPC 错误信封，通过则回 SSE 帧迭代器。

    返回 ``dict`` 而非抛异常，是因为调用方（视图层）要据此决定**不进入 SSE**：一旦响应头写成
    ``text/event-stream``，HTTP 状态与 ``Retry-After`` 就都没处放了。

    前置失败一律先留一条审计再回信封：这些调用没有流，终态帧的审计路径不会走到。
    """
    started = time.monotonic()
    req_id: object = payload.get("id") if isinstance(payload, dict) else None
    if not isinstance(payload, dict) or "method" not in payload:
        await _audit_failure(ctx, agent_id, INVALID_REQUEST, started)
        return jsonrpc_error(req_id, INVALID_REQUEST, "非法 JSON-RPC 请求")
    params = payload.get("params")
    if not isinstance(params, dict):
        await _audit_failure(ctx, agent_id, INVALID_PARAMS, started)
        return jsonrpc_error(req_id, INVALID_PARAMS, "tasks/resubscribe 缺少 params")
    try:
        await load_published_agent(db, agent_id)
    except NotFoundError as exc:
        # 与 message/stream 的智能体门槛同口径：未发布 / 不存在都回参数类错误码，
        # 而不是「任务不存在」—— 后者会把「智能体没发布」误报成「任务找不到」。
        await _audit_failure(ctx, agent_id, INVALID_PARAMS, started)
        return jsonrpc_error(req_id, INVALID_PARAMS, str(exc))
    try:
        job_id = parse_task_id(params)
        job = await load_owned_agent_task(db, ctx, agent_id, job_id)
    except BadRequestError as exc:
        await _audit_failure(ctx, agent_id, INVALID_PARAMS, started)
        return jsonrpc_error(req_id, INVALID_PARAMS, str(exc))
    except NotFoundError as exc:
        # 不区分「不存在 / 不属于该智能体 / 是合成的流式 id / 属于外租户」：一律按任务不存在
        # 回，不向对端确认任务是否存在。外租户那一路由 load_owned_agent_task 归一（见其注释）。
        await _audit_failure(ctx, agent_id, TASK_NOT_FOUND, started)
        return jsonrpc_error(req_id, TASK_NOT_FOUND, str(exc))
    # 结束请求级事务并归还连接：订阅最长 30 分钟，不主动结束就会有一条连接陪跑。
    # 用 ``commit`` 而非 ``rollback``：鉴权依赖在同一会话里 flush 了 API Key 的
    # ``last_used_at``（``touch_last_used`` 的契约就是「由调用方提交」），rollback 会把
    # 这笔记账丢掉。
    await db.commit()
    return _subscription_frames(
        ctx=ctx,
        agent_id=agent_id,
        req_id=req_id,
        base_url=base_url,
        job_id=job_id,
        context_id=context_id_from_job_params(job.params),
        started=started,
    )


async def _audit_failure(ctx: TenantContext, agent_id: UUID, error_code: int, started: float) -> None:
    """前置失败的留痕，口径与 ``message/stream`` 的 ``_audit_stream_preflight`` 一致。

    不记就出现「同一个非法调用，``message/send`` / ``message/stream`` 有迹、
    ``tasks/resubscribe`` 零痕迹」，探测式调用可以不留痕迹。
    """
    await write_a2a_audit(
        ctx=ctx,
        agent_id=agent_id,
        action=AUDIT_ACTION_TASKS_RESUBSCRIBE,
        outcome=AUDIT_OUTCOME_FAILED,
        detail={
            "method": "tasks/resubscribe",
            "errorCode": error_code,
            "durationMs": streaming.elapsed_ms(started),
        },
    )


async def _subscription_frames(
    *,
    ctx: TenantContext,
    agent_id: UUID,
    req_id: object,
    base_url: str,
    job_id: UUID,
    context_id: str | None,
    started: float,
) -> AsyncIterator[str]:
    """订阅帧生成器：首帧 ``Task`` 快照，其后只在确有变化时发帧，其余发保活帧。"""
    #: 本方法的 taskId 就是真实 job id（与 message/stream 的合成 id 不同）
    task_id = str(job_id)
    latest_state = TASK_STATE_UNKNOWN
    audit_state: dict[str, str] = {}

    def schedule_audit_once(audit_outcome: str, *, ended_by: str, task_state: str) -> None:
        """调度本次订阅的留痕：同步、幂等、脱离取消作用域。

        三条缺一不可，理由与 ``message/stream`` 的 ``schedule_stream_audit`` 完全相同
        （见 ``services/server.py`` 的注释），差别只在 ``detail`` 多 ``endedBy`` / ``taskState``。
        """
        if audit_state:
            return
        audit_state["outcome"] = audit_outcome
        detail: dict = {
            "method": "tasks/resubscribe",
            "taskId": task_id,
            "taskState": task_state,
            "endedBy": ended_by,
            "durationMs": streaming.elapsed_ms(started),
        }
        if context_id:
            detail["contextId"] = context_id
        schedule_audit(
            write_a2a_audit(
                ctx=ctx,
                agent_id=agent_id,
                action=AUDIT_ACTION_TASKS_RESUBSCRIBE,
                outcome=audit_outcome,
                detail=detail,
            )
        )

    def status_frame(*, state: str, text: str | None, percent: object, final: bool) -> str:
        return streaming.sse_frame(
            jsonrpc_result(
                req_id,
                build_a2a_status_update(
                    task_id=task_id,
                    context_id=context_id,
                    state=state,
                    timestamp=now_iso(),
                    text=text,
                    final=final,
                    percent=percent,
                ),
            )
        )

    async def reload_job() -> GenerativeJob:
        # 短开短关：30 分钟上限下绝不能让一条连接陪跑整段流（与 message/stream 的轮次会话同法）。
        async with AsyncSessionLocal() as session:
            return await get_generative_job_for_tenant(session, ctx, job_id)

    jobs = watch_generative_job(
        job_id=job_id,
        tenant_id=ctx.tenant_id,
        reload=reload_job,
        is_terminal=lambda job: is_terminal_generative_status(str(job.status.value)),
        max_seconds=SUBSCRIPTION_MAX_SECONDS,
        poll_interval=SUBSCRIPTION_POLL_SECONDS,
        emit_ticks=True,
    )
    try:
        first = await anext(jobs)
        if first is None:
            # 契约保证走不到：刻度只在订阅建立**之后**产出，首产出必是 reload 快照。
            # 真走到说明契约被改坏，按「拿不到快照」收尾，不让内部错误变成 500。
            schedule_audit_once(AUDIT_OUTCOME_FAILED, ended_by="failed", task_state=TASK_STATE_UNKNOWN)
            return
        latest_job = first
        latest_state = to_a2a_task_state(str(first.status.value))
        terminal_at_subscribe = is_terminal_generative_status(str(first.status.value))
        yield streaming.sse_frame(
            jsonrpc_result(
                req_id,
                build_a2a_task(
                    task_id=task_id,
                    context_id=context_id,
                    state=latest_state,
                    timestamp=now_iso(),
                    # 订阅时已终态：产物直接挂首帧（一帧讲完整段故事）；否则本次订阅期间产出的
                    # 走 artifact-update 帧，同一产物不在一条流里出现两次。
                    artifacts=(
                        build_a2a_artifacts(job_result=first.result, agent_id=agent_id, task_id=job_id, base_url=base_url) if terminal_at_subscribe else None
                    ),
                ),
            )
        )
        if terminal_at_subscribe:
            schedule_audit_once(
                _TERMINAL_OUTCOME.get(latest_state, AUDIT_OUTCOME_FAILED),
                ended_by="terminal",
                task_state=latest_state,
            )
            yield status_frame(
                state=latest_state,
                text=progress_text(progress_message=first.progress_message, percent=first.progress_percent),
                percent=first.progress_percent,
                final=True,
            )
            return

        fingerprint = _progress_fingerprint(first)
        async for job in jobs:
            if job is None:
                # 空闲刻度：下发保活帧（SSE 注释行），对端与中间代理据此知道连接还活着。
                yield streaming.SSE_HEARTBEAT_FRAME
                continue
            latest_job = job
            latest_state = to_a2a_task_state(str(job.status.value))
            if is_terminal_generative_status(str(job.status.value)):
                for artifact in build_a2a_artifacts(job_result=job.result, agent_id=agent_id, task_id=job_id, base_url=base_url):
                    yield streaming.sse_frame(
                        jsonrpc_result(
                            req_id,
                            build_a2a_artifact_update(task_id=task_id, context_id=context_id, artifact=artifact),
                        )
                    )
                schedule_audit_once(
                    _TERMINAL_OUTCOME.get(latest_state, AUDIT_OUTCOME_FAILED),
                    ended_by="terminal",
                    task_state=latest_state,
                )
                yield status_frame(
                    state=latest_state,
                    text=progress_text(progress_message=job.progress_message, percent=job.progress_percent),
                    percent=job.progress_percent,
                    final=True,
                )
                return
            current = _progress_fingerprint(job)
            if current == fingerprint:
                # 没有新信息：发保活帧而不是重复帧 —— 重复帧只会让对端以为自己落后了。
                yield streaming.SSE_HEARTBEAT_FRAME
                continue
            fingerprint = current
            yield status_frame(
                state=latest_state,
                text=progress_text(progress_message=job.progress_message, percent=job.progress_percent),
                percent=job.progress_percent,
                final=False,
            )
        # 循环结束仍未见终态：安全上限（设计 §3.5）。状态取断点时的**真实**映射值，
        # 不谎报成 completed —— 对端据此决定是否再订阅一次。
        # 必须留 warning：30 分钟上限是对规范的有意偏离，审计行只在租户审计页可见，
        # 不落日志就等于「病态任务占住连接半小时」在运维侧完全不可见。只记元数据。
        logger.warning(
            "A2A tasks/resubscribe 触达安全上限，按当前状态收流 (agent_id=%s task_id=%s state=%s max_seconds=%s)",
            agent_id,
            task_id,
            latest_state,
            SUBSCRIPTION_MAX_SECONDS,
        )
        schedule_audit_once(AUDIT_OUTCOME_OK, ended_by="safety-cap", task_state=latest_state)
        yield status_frame(
            state=latest_state,
            text=progress_text(progress_message=latest_job.progress_message, percent=latest_job.progress_percent),
            percent=latest_job.progress_percent,
            final=True,
        )
    except (GeneratorExit, asyncio.CancelledError):
        # 对端断连（``aclose()``）或真实断连（Starlette 取消消费任务）：终态帧不会再发，但留痕
        # 要在这里补上 ——「谁中途掐了连接」正是审计要回答的问题之一。只能同步调度、不能再 yield。
        schedule_audit_once(AUDIT_OUTCOME_CANCELED, ended_by="disconnect", task_state=latest_state)
        raise
    except Exception:
        # 订阅期间的非预期异常（任务在流中途被删、Redis 与 DB 同时不可用）：回一帧 failed 终态
        # 再收流 —— 绝不让对端等到「流突然断掉却没有终态帧」，也不让留痕丢在这条路径上。
        logger.exception("A2A tasks/resubscribe 订阅中断: agent_id=%s task_id=%s", agent_id, task_id)
        schedule_audit_once(AUDIT_OUTCOME_FAILED, ended_by="failed", task_state=TASK_STATE_FAILED)
        yield status_frame(state=TASK_STATE_FAILED, text="订阅中断", percent=None, final=True)
    finally:
        # 内层生成器不随外层关闭自动清理（正常收流时它还挂在 get_message 上，redis 订阅要到 GC
        # 才撤）：显式 aclose 触发它的 finally 取消订阅。已耗尽时是无操作。
        await jobs.aclose()
