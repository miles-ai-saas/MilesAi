"""A2A Server：``message/stream`` SSE 真流。

经 ``server`` 门面 re-export；对话与审计依赖经 ``server`` 模块属性解析，
以便单测 monkeypatch 路径与拆分前一致。
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.exceptions import BadRequestError, NotFoundError
from miles_common.schemas.chat_io import ChatMediaIn
from miles_core.logging import get_logger
from miles_core.tenant import TenantContext
from miles_portal.tenant.a2a.server import (
    AUDIT_ACTION_MESSAGE_STREAM,
    AUDIT_OUTCOME_CANCELED,
    AUDIT_OUTCOME_FAILED,
    AUDIT_OUTCOME_OK,
    AUDIT_OUTCOME_REJECTED,
    INVALID_PARAMS,
    INVALID_REQUEST,
    TASK_STATE_COMPLETED,
    TASK_STATE_FAILED,
    TASK_STATE_REJECTED,
    TASK_STATE_WORKING,
    build_a2a_status_update,
    build_a2a_task,
    extract_message_context_id,
    jsonrpc_error,
    jsonrpc_result,
    now_iso,
)
from miles_portal.tenant.a2a.services import streaming
from miles_portal.tenant.a2a.services.audit import schedule_audit
from miles_portal.tenant.a2a.services.inbound_parts import resolve_inbound_chat_input

logger = get_logger(__name__)

#: SSE 帧之间的增量队列上限。满时 ``on_delta`` 会等待消费者 —— 对上游形成背压，
#: 否则慢消费者 + 长回答会把队列撑成无界缓冲。
STREAM_QUEUE_MAXSIZE = 64

#: 与「产出一片空串」区分的收尾哨兵。
_STREAM_DONE = object()

#: 流式终态 → 审计 ``outcome``。``working`` 是「本流结束但任务还在跑」（对端转
#: ``tasks/get`` 轮询），对审计而言属正常完成。
_STREAM_OUTCOME_BY_STATE = {
    TASK_STATE_COMPLETED: AUDIT_OUTCOME_OK,
    TASK_STATE_WORKING: AUDIT_OUTCOME_OK,
    TASK_STATE_FAILED: AUDIT_OUTCOME_FAILED,
    TASK_STATE_REJECTED: AUDIT_OUTCOME_REJECTED,
}


def _stream_audit_detail(*, started: float, context_id: str, task_id: str) -> dict:
    """``message/stream`` 中途（终态帧 / 断连）审计的 ``detail``。

    只含元数据，**绝不含消息正文**（``aud_logs`` 是租户可见面）；三处调用点共用它，
    形状与口径只在这里维护一次。
    """
    return {"method": "message/stream", "contextId": context_id, "taskId": task_id, "durationMs": streaming.elapsed_ms(started)}


def _failure_text(error: Exception) -> str:
    """失败终态给对端的可读原因：``BadRequestError`` 的 message 本就可读，其余统一前缀。"""
    if isinstance(error, BadRequestError):
        return error.message
    return f"智能体执行失败: {error}"


async def _audit_stream_preflight(ctx: TenantContext, agent_id: UUID, error_code: int, started: float) -> None:
    """``message/stream`` 前置失败的审计：与 send 侧**可达的**参数类失败对称。

    口径用 ``failed`` 与 ``message/send`` 对齐；``rejected`` 专指智能体/合规拒绝处理。
    """
    from miles_portal.tenant.a2a.services import server as svc

    await svc.write_a2a_audit(
        ctx=ctx,
        agent_id=agent_id,
        action=AUDIT_ACTION_MESSAGE_STREAM,
        outcome=AUDIT_OUTCOME_FAILED,
        detail={"method": "message/stream", "errorCode": error_code, "durationMs": streaming.elapsed_ms(started)},
    )


async def open_a2a_stream(
    db: AsyncSession,
    ctx: TenantContext,
    agent_id: UUID,
    payload: object,
) -> dict | AsyncIterator[str]:
    """``message/stream`` 入口：前置校验失败回 JSON-RPC 错误信封，通过则回 SSE 帧迭代器。

    返回 ``dict`` 而非抛异常，是因为调用方（视图层）要据此决定**不进入 SSE**：一旦
    响应头写成 ``text/event-stream``，HTTP 状态与 Content-Type 已定，错误只能塞进帧里，
    对端解析反而更麻烦。

    前置失败一律先留一条审计再回信封：这些调用没有 SSE 流，终态帧的审计路径不会走到。
    """
    from miles_portal.tenant.a2a.services import server as svc

    started = time.monotonic()
    req_id: object = payload.get("id") if isinstance(payload, dict) else None
    if not isinstance(payload, dict) or "method" not in payload:
        await svc._audit_stream_preflight(ctx, agent_id, INVALID_REQUEST, started)
        return jsonrpc_error(req_id, INVALID_REQUEST, "非法 JSON-RPC 请求")
    params = payload.get("params")
    if not isinstance(params, dict):
        await svc._audit_stream_preflight(ctx, agent_id, INVALID_PARAMS, started)
        return jsonrpc_error(req_id, INVALID_PARAMS, "message/stream 缺少 params")
    try:
        await svc.load_published_agent(db, agent_id)
        inbound = await resolve_inbound_chat_input(db, ctx, params, agent_id=agent_id)
        # 未带 contextId 时生成一个：首轮就得用它，否则第一轮 checkpoint 落在别的
        # thread，对端第二轮带上该 id 时模型并无上一轮记忆。
        context_id = extract_message_context_id(params) or str(uuid4())
    except (NotFoundError, BadRequestError) as exc:
        await svc._audit_stream_preflight(ctx, agent_id, INVALID_PARAMS, started)
        return jsonrpc_error(req_id, INVALID_PARAMS, str(exc))
    # 结束请求级事务并归还连接：``yield`` 依赖的 teardown 要等整条响应发完才跑，而流可能
    # 持续数分钟，不主动结束就会有一条连接陪跑（轮次自身还会另开一条）。
    # 用 ``commit`` 而非 ``rollback``：同一会话里鉴权依赖已 ``flush`` 了 API Key 的
    # ``last_used_at``（``touch_last_used`` 的契约就是「由调用方决定提交」），rollback 会把
    # 这笔记账丢掉，让流式调用在「密钥最后使用时间」上永远不更新。
    # 入站附件也已在本事务落库，须一并 commit，否则流式轮次读不到刚上传的图。
    await db.commit()
    return svc._stream_turn(
        ctx,
        agent_id,
        req_id,
        inbound.query,
        context_id,
        media=inbound.media,
    )


async def _stream_turn(
    ctx: TenantContext,
    agent_id: UUID,
    req_id: object,
    text: str,
    context_id: str,
    *,
    media: list[ChatMediaIn] | None = None,
) -> AsyncIterator[str]:
    """跑一轮对话并以 SSE 帧下发：首帧 Task、中间帧增量、末帧终态。"""
    from miles_portal.tenant.a2a.services import server as svc

    started = time.monotonic()
    task_id = str(uuid4())
    queue: asyncio.Queue[object] = asyncio.Queue(maxsize=STREAM_QUEUE_MAXSIZE)
    outcome: dict[str, object] = {}
    stopped = False
    #: 本次调用的审计是否已调度（终态或取消）。只作幂等哨兵，值本身不参与判定；因为它在
    #: 任何 ``await`` 之前就同步置位，「取消」与「终态」不可能各调度一次。
    audit_state: dict[str, str] = {}

    def schedule_stream_audit(audit_outcome: str) -> None:
        """调度本次 ``message/stream`` 调用的审计。同步、幂等、脱离取消作用域。

        三条缺一不可（每条都对应一次实测到的坏结果）：
        1. **同步**：必须在调用点任何 ``await`` 之前完成。调度若含 ``await``，取消就能插进
           「终态已定」与「已调度」之间 —— ``ok`` 与 ``canceled`` 都写不成，一次调用零流水。
        2. **幂等**：终态帧与取消分支争的是「一次调用恰一条流水」；哨兵同步置位，后到者直接返回。
           置位若放在写入 ``await`` 之后，就会出现「``ok`` 已落库、取消又补一条」的双流水。
        3. **脱离取消作用域**：写入交 ``services.audit.schedule_audit`` 起独立 task。取消作用域（Starlette /
           anyio 走的正是它）会在任务真正结束前反复取消，直接 ``await write_a2a_audit`` 会被
           立刻再次取消，流水同样丢失。
        """
        if audit_state:
            return
        audit_state["outcome"] = audit_outcome
        schedule_audit(
            svc.write_a2a_audit(
                ctx=ctx,
                agent_id=agent_id,
                action=AUDIT_ACTION_MESSAGE_STREAM,
                outcome=audit_outcome,
                detail=_stream_audit_detail(started=started, context_id=context_id, task_id=task_id),
            )
        )

    async def terminal_frame(state: str, frame_text: str, *, job_task_id: str | None = None) -> str:
        """终态帧 + 审计：``message/stream`` 的 outcome 只有走到终态才知道。

        审计的调度是**本函数第一件事**（见 ``schedule_stream_audit``）：此后无论对端怎么断，
        这次调用都已经有流水在飞了。
        """
        schedule_stream_audit(_STREAM_OUTCOME_BY_STATE[state])
        return streaming.sse_frame(
            jsonrpc_result(
                req_id,
                build_a2a_status_update(
                    task_id=task_id,
                    context_id=context_id,
                    state=state,
                    timestamp=now_iso(),
                    text=frame_text,
                    final=True,
                    job_task_id=job_task_id,
                ),
            )
        )

    async def on_delta(piece: str) -> None:
        # 空片不发帧：与 ws/chat.on_delta 同判定，省掉无内容的帧（含空格的片照发，
        # 它可能是词间分隔）。
        if piece:
            await queue.put(piece)

    async def run_turn() -> None:
        # 自开会话：整轮对话要跨流式多次读库并在末尾 commit，依赖 get_db 依赖的
        # 回收时序不可靠（与 ws/chat._run_chat_turn 同法）。
        try:
            async with svc.AsyncSessionLocal() as turn_db:
                try:
                    outcome["response"] = await svc.run_published_agent_chat(
                        turn_db,
                        ctx,
                        agent_id,
                        text,
                        media=media,
                        conversation_id=context_id,
                        on_delta=on_delta,
                    )
                    await turn_db.commit()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    outcome["error"] = exc
                    # chat() 失败时已自 commit 过失败/拦截记录，此处 rollback 只为清掉残留。
                    await turn_db.rollback()
                    logger.exception("A2A message/stream 执行失败: agent_id=%s", agent_id)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # 连会话都开不起来（引擎/驱动问题）：也要记进 outcome，否则生成器只能靠
            # 「error 与 response 都空」去推断，且任务异常无人 retrieve 会打噪音日志。
            outcome["error"] = exc
            logger.exception("A2A message/stream 无法建立会话: agent_id=%s", agent_id)
        finally:
            # 哨兵必须等会话关闭之后才入队：``async with`` 的退出（``AsyncSession.close()``）
            # 会让出控制权，若哨兵已经躺在队列里，生成器会在那一刻醒来并 ``cancel()`` 本任务，
            # 把正在关闭的会话打断 —— 连接就只能等 GC 兜底归还连接池。
            if not stopped:
                await queue.put(_STREAM_DONE)

    turn = asyncio.create_task(run_turn())
    try:
        yield streaming.sse_frame(
            jsonrpc_result(
                req_id,
                build_a2a_task(
                    task_id=task_id,
                    context_id=context_id,
                    state=TASK_STATE_WORKING,
                    timestamp=now_iso(),
                ),
            )
        )
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=streaming.SSE_HEARTBEAT_SECONDS)
            except TimeoutError:
                # 保活：注释帧不进入 JSON 序列，对端解析器忽略它，只用于维持连接。
                yield streaming.SSE_HEARTBEAT_FRAME
                continue
            if item is _STREAM_DONE:
                break
            yield streaming.sse_frame(
                jsonrpc_result(
                    req_id,
                    build_a2a_status_update(
                        task_id=task_id,
                        context_id=context_id,
                        state=TASK_STATE_WORKING,
                        timestamp=now_iso(),
                        text=item,
                        final=False,
                    ),
                )
            )
        # 终态帧也留在 ``try`` 内：它是「已调度审计」之后唯一还可能被抛入取消的 `yield``。
        # 搬进来之后取消分支才有机会看到已置位的哨兵，``audit_state`` 由兜底变为承重件（见
        # ``schedule_stream_audit`` 第 2 条）：终态已调度时再被取消，恰好不会再补一条 canceled。
        error = outcome.get("error")
        response = outcome.get("response")
        if error is not None:
            state = TASK_STATE_REJECTED if isinstance(error, BadRequestError) else TASK_STATE_FAILED
            yield await terminal_frame(state, _failure_text(error))
            return
        if response is None:
            # 兜底：error 与 response 同时为空，只可能来自「任务在记录 outcome 之前就没了」。
            # 回一帧 failed 终态，别让对端等到「流自然结束却没有终态帧」而只能超时。
            yield await terminal_frame(TASK_STATE_FAILED, "智能体执行失败")
            return
        job = svc._first_active_job(response.generative_jobs)
        if job:
            # 产物未就绪：以 working + final 收尾（final 只表示本流结束），并给出真实
            # job id —— 对端据此转向 tasks/get 轮询状态与产物。
            yield await terminal_frame(TASK_STATE_WORKING, response.answer, job_task_id=str(job["id"]))
            return
        yield await terminal_frame(TASK_STATE_COMPLETED, response.answer)
    except GeneratorExit:
        # 对端断连（``aclose()``）：生成器被抛入 GeneratorExit，后面的终态帧不会再发，但留痕
        # 要在这里补上 —— 「谁中途掐了连接」正是审计要回答的问题之一。这里只能同步调度、
        # 不能再 ``yield``；调度本身不 ``await``，故 ``aclose()`` 路径下也能完成。
        schedule_stream_audit(AUDIT_OUTCOME_CANCELED)
        raise
    except asyncio.CancelledError:
        # 真实断连走的是这一条：客户端断连时 Starlette 取消的正是「``async for`` 迭代本生成器」
        # 那个任务，``CancelledError`` 直接抛在生成器长期挂着的 ``await``（等下一个增量）处，
        # ``GeneratorExit`` 根本不会触发 —— 只处理后者会让最常见的断连永久零痕迹。
        # 两条分支行为一致（调度 canceled 后 ``raise``），但都必须保留：它们由不同的异常类型
        # 触发，``except (GeneratorExit, CancelledError)`` 一旦被后人合并再改错也未必看得出。
        schedule_stream_audit(AUDIT_OUTCOME_CANCELED)
        raise
    finally:
        # 消费端提前退出（客户端断连）：必须取消对话任务，否则 LLM 调用会跑到底白烧 token。
        # 先置 stopped 再取消：让 run_turn 的 finally 不再往无人消费的队列里塞哨兵。
        # 注意：终态帧已在 ``try`` 内，正常走完时本 ``finally`` 会在终态 ``yield`` **之后**
        # 执行（对话任务通常已 done，下面的 ``cancel`` 是空操作）；取消分支则在哨兵已置位
        # 之后进入这里 —— 两种时序下都只需清场，不必再碰审计。
        stopped = True
        if not turn.done():
            turn.cancel()
