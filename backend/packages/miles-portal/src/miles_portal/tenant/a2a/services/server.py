"""A2A Server 用例层门面：发布门槛、Card、JSON-RPC 分发（``message/send`` / ``tasks/*``）。

实现按职责拆到 ``server_publish`` / ``server_tasks`` / ``server_stream``；本模块保留
RPC 入口与 ``message/send``，并 re-export 公共符号供 API 层与单测
``monkeypatch.setattr(server_svc, ...)`` 使用。

鉴权边界
--------
Card 是公开发现元数据（A2A 约定，且 ``card_client.fetch_agent_card`` 不带凭证），故
Card GET 无鉴权，仅由 ``config.a2a_publish`` 门槛约束可见性；调用端点 ``message/send``
必须带该智能体的 ``X-API-Key``（复用 ``require_agent_api_key``）。
"""

from __future__ import annotations

import time
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.exceptions import AppError, BadRequestError, NotFoundError
from miles_common.schemas.chat_io import CONVERSATION_ID_MAX_LENGTH, ChatMediaIn, ChatResponse
from miles_core.infra.db import AsyncSessionLocal
from miles_core.logging import get_logger
from miles_core.soft_delete import is_marked_deleted
from miles_core.tenant import TenantContext
from miles_integrations.langchain.chat_models import OnDelta
from miles_portal.tenant.a2a.server import (
    AUDIT_ACTION_MESSAGE_SEND,
    AUDIT_ACTION_PUSH_CONFIG_DELETE,
    AUDIT_ACTION_PUSH_CONFIG_GET,
    AUDIT_ACTION_PUSH_CONFIG_LIST,
    AUDIT_ACTION_PUSH_CONFIG_SET,
    AUDIT_ACTION_TASKS_CANCEL,
    AUDIT_ACTION_TASKS_GET,
    AUDIT_OUTCOME_FAILED,
    AUDIT_OUTCOME_OK,
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    PUSH_NOTIFICATION_METHODS,
    app_error_envelope,
    build_a2a_agent_message,
    build_a2a_task,
    extract_message_context_id,
    is_active_generative_status,
    jsonrpc_error,
    jsonrpc_result,
    now_iso,
    to_a2a_task_state,
)
from miles_portal.tenant.a2a.services import streaming
from miles_portal.tenant.a2a.services.audit import write_a2a_audit
from miles_portal.tenant.a2a.services.inbound_parts import resolve_inbound_chat_input
from miles_portal.tenant.a2a.services.server_publish import (
    _bound_skill_entries,
    build_agent_card_by_id,
    build_public_agent_card,
    is_agent_published,
    load_published_agent,
    resolve_default_published_agent_id,
)
from miles_portal.tenant.a2a.services.server_stream import (
    _audit_stream_preflight,
    _stream_turn,
    open_a2a_stream,
)
from miles_portal.tenant.a2a.services.server_tasks import (
    _audit_artifact_failure,
    _handle_tasks_cancel,
    _handle_tasks_get,
    load_owned_agent_task,
    parse_task_id,
    read_task_artifact,
)
from miles_portal.tenant.attachments.services.attachment import AttachmentService
from miles_portal.tenant.generative.services.job import GenerativeJobService
from miles_portal.tenant.generative.services.job_execution import get_generative_job_for_tenant

logger = get_logger(__name__)

# 供子模块经 ``server`` 属性解析（单测 monkeypatch 目标）。
__all__ = [
    "AsyncSessionLocal",
    "AttachmentService",
    "GenerativeJobService",
    "_audit_artifact_failure",
    "_audit_stream_preflight",
    "_bound_skill_entries",
    "_dispatch_a2a_rpc",
    "_first_active_job",
    "_stream_turn",
    "build_agent_card_by_id",
    "build_public_agent_card",
    "context_id_from_job_params",
    "get_generative_job_for_tenant",
    "handle_a2a_rpc",
    "is_agent_published",
    "is_marked_deleted",
    "load_owned_agent_task",
    "load_published_agent",
    "open_a2a_stream",
    "parse_task_id",
    "read_task_artifact",
    "resolve_default_published_agent_id",
    "run_published_agent_chat",
    "write_a2a_audit",
]


async def run_published_agent_chat(
    db: AsyncSession,
    ctx: TenantContext,
    agent_id: UUID,
    text: str,
    *,
    media: list[ChatMediaIn] | None = None,
    conversation_id: str | None = None,
    on_delta: OnDelta | None = None,
) -> ChatResponse:
    """入站 A2A 任务 → 平台对话链路，返回完整对话响应（含异步生成任务）。

    ``conversation_id`` 来自 A2A ``message.contextId``，作为同一会话的 ``thread_id``
    后缀恢复 LangGraph checkpoint，从而支持多轮。

    ``media`` 来自入站 ``file`` parts（图片已落库为附件）；与平台 Chat 同源。

    ``on_delta`` 为真流回调（``message/stream`` 用）：逐 token 交给调用方下发；不传则
    只在返回时一次性拿到完整回答（``message/send`` 与不支持真流的路由都走这条）。

    返回整个 ``ChatResponse`` 而非仅 ``answer``：产生异步生成任务时须据此回 A2A
    ``Task`` 供对端轮询。

    函数内 import ``AgentService``：``agents.services.agent`` 依赖 ``a2a`` 域内的
    peer_refs / invoke，模块级互引会成环。
    """
    from miles_portal.tenant.agents.schemas.agent import ChatRequest
    from miles_portal.tenant.agents.services.agent import AgentService

    return await AgentService(db, ctx).chat(
        agent_id,
        ChatRequest(query=text, media=list(media or []), conversation_id=conversation_id),
        on_delta=on_delta,
    )


def context_id_from_job_params(params: object) -> str | None:
    """从生成任务参数快照取会话标识，作为 ``Task.contextId`` 回给对端。

    委托 ``chat_artifact_sync`` 的同一解析（键约定只有一个来源），取不到则省略该字段。
    """
    from miles_portal.tenant.agents.services.chat_artifact_sync import conversation_id_from_job_params

    return conversation_id_from_job_params(params)


def _first_active_job(jobs: list[dict]) -> dict | None:
    """对话响应中第一个仍在进行且带 id 的生成任务条目（终态任务无需对端轮询）。"""
    for job in jobs:
        if isinstance(job, dict) and job.get("id") and is_active_generative_status(job.get("status")):
            return job
    return None


def _agent_message(text: str, context_id: str) -> dict:
    """A2A ``Message``（agent 角色）。形状由纯逻辑模块单一维护，此处不再另抄一份。"""
    return build_a2a_agent_message(text=text, context_id=context_id)


async def _handle_message_send(
    db: AsyncSession,
    ctx: TenantContext,
    agent_id: UUID,
    req_id: object,
    params: dict,
) -> dict:
    """``message/send``：执行对话；产生异步生成任务则回 ``Task``，否则回 ``Message``。"""
    try:
        await load_published_agent(db, agent_id)
        inbound = await resolve_inbound_chat_input(db, ctx, params, agent_id=agent_id)
        # 未带 contextId 时生成一个并回显：对端才有可复用的上下文标识，多轮才接得上。
        context_id = extract_message_context_id(params) or str(uuid4())
    except (NotFoundError, BadRequestError) as exc:
        return jsonrpc_error(req_id, INVALID_PARAMS, str(exc))

    try:
        response = await run_published_agent_chat(
            db,
            ctx,
            agent_id,
            inbound.query,
            media=inbound.media,
            conversation_id=context_id,
        )
    except AppError:
        # 业务异常（合规拦截的 BadRequestError、配额的 ForbiddenError …）不在此处译码：交给
        # ``handle_a2a_rpc`` 的统一兜底 —— 既拿到一致的域映射（都在 ``message/send`` 域，故为
        # -32602），也让审计能记下原始 ``errorType``/``errorStatus``。若在这里吞成 -32603，
        # 「配额用尽」「命中敏感词」都会被报成「服务端内部错误」，对端会去重试。
        raise
    except Exception as exc:
        # 对端只拿到 JSON-RPC 错误信封；本平台侧必须留栈，否则线上无法定位。
        logger.exception("A2A message/send 执行失败: agent_id=%s", agent_id)
        return jsonrpc_error(req_id, INTERNAL_ERROR, f"智能体执行失败: {exc}")

    job = _first_active_job(response.generative_jobs)
    if job:
        # 产物未就绪：回 Task 让对端可 tasks/get 轮询、tasks/cancel 取消。状态照实映射
        # （pending → submitted / running → working），不一律报 working。
        return jsonrpc_result(
            req_id,
            build_a2a_task(
                task_id=str(job.get("id")),
                context_id=context_id,
                state=to_a2a_task_state(str(job.get("status"))),
                timestamp=now_iso(),
            ),
        )
    return jsonrpc_result(req_id, _agent_message(response.answer, context_id))


#: JSON-RPC 方法 → 租户审计 ``action``。``message/stream`` 不在此表：它的 outcome 只有
#: 终态帧才知道，由 ``_stream_turn`` 自己写。不支持的方法没有对应动作名，不编造流水。
_AUDIT_ACTION_BY_METHOD = {
    "message/send": AUDIT_ACTION_MESSAGE_SEND,
    "tasks/get": AUDIT_ACTION_TASKS_GET,
    "tasks/cancel": AUDIT_ACTION_TASKS_CANCEL,
    "tasks/pushNotificationConfig/set": AUDIT_ACTION_PUSH_CONFIG_SET,
    "tasks/pushNotificationConfig/get": AUDIT_ACTION_PUSH_CONFIG_GET,
    "tasks/pushNotificationConfig/list": AUDIT_ACTION_PUSH_CONFIG_LIST,
    "tasks/pushNotificationConfig/delete": AUDIT_ACTION_PUSH_CONFIG_DELETE,
}


async def handle_a2a_rpc(
    db: AsyncSession,
    ctx: TenantContext,
    agent_id: UUID,
    payload: object,
    *,
    base_url: str,
) -> dict:
    """JSON-RPC 2.0 分发入口：分发并统一留租户审计。

    审计放在这一层而非各 ``_handle_*`` 内：一次调用只该有一条流水，且 ``outcome`` 由最终
    信封决定（有 ``error`` 即失败），不必在各处重复判定。

    ``AppError`` 在这一层收口：各 ``_handle_*`` 的逐点映射是第一道（语义更精确），但只要
    某个 handler 漏捕、或捕得比业务异常更宽，异常就会落到 ``except AppError`` 被译成
    JSON-RPC 信封 —— 对端拿到的形状与逐点映射一致，且尾部那条统一审计能把原始类型与
    状态码记进 ``detail.errorType`` / ``detail.errorStatus``。
    """
    started = time.monotonic()
    method = payload.get("method") if isinstance(payload, dict) else None
    req_id = payload.get("id") if isinstance(payload, dict) else None
    action = _AUDIT_ACTION_BY_METHOD.get(method) if isinstance(method, str) else None
    # ``action`` 非空只可能来自「``method`` 是表内键」，此处重判一次让 ``method`` 收窄为
    # ``str``，不给调用点留下「靠运气成立」的类型不一致。
    if action is None or not isinstance(method, str):
        # 不支持的方法没有对应动作名，不编造流水。
        return await _dispatch_a2a_rpc(db, ctx, agent_id, payload, base_url=base_url)
    #: 被兜底接住的业务异常。非空时把原始类型与 status 记进审计（对外码已被压平）。
    origin: AppError | None = None
    try:
        envelope = await _dispatch_a2a_rpc(db, ctx, agent_id, payload, base_url=base_url)
    except AppError as exc:
        # 只有 handler 漏捕或捕得更宽才会走到这里 —— 是「映射归属」漏了，值得可查。
        origin = exc
        logger.warning(
            "A2A 业务异常经兜底译码: method=%s agent_id=%s errorType=%s status=%s",
            method,
            agent_id,
            type(exc).__name__,
            exc.status_code,
        )
        envelope = app_error_envelope(method, req_id, exc)
    except Exception:
        # 未捕获异常逸出（DB / 存储故障）：先留痕再**原样重抛**。这里是失败路径上唯一的
        # 留痕机会 —— 吞掉异常会把 500 变成 200，把故障伪装成成功。
        # detail 走 ``_rpc_audit_detail``：``contextId`` 与正常路径同一长度闸口，避免兑底
        # 路径把超长值写进租户可见面、或漏掉本可取到的会话标识。
        await write_a2a_audit(
            ctx=ctx,
            agent_id=agent_id,
            action=action,
            outcome=AUDIT_OUTCOME_FAILED,
            detail=_rpc_audit_detail(
                payload,
                {"error": {"code": INTERNAL_ERROR}},
                started=started,
                method=method,
            ),
        )
        raise
    await write_a2a_audit(
        ctx=ctx,
        agent_id=agent_id,
        action=action,
        outcome=_rpc_audit_outcome(envelope),
        detail=_rpc_audit_detail(payload, envelope, started=started, method=method, origin=origin),
    )
    return envelope


def _rpc_audit_outcome(envelope: object) -> str:
    """按最终信封判定结果：有 ``error`` 即失败（协议级错误也不例外）。"""
    return AUDIT_OUTCOME_FAILED if isinstance(envelope, dict) and "error" in envelope else AUDIT_OUTCOME_OK


def _rpc_audit_detail(payload: object, envelope: object, *, started: float, method: str, origin: AppError | None = None) -> dict:
    """审计细节：方法、耗时，以及能低成本取到的任务/会话标识与错误码。

    ``origin`` 非空表示该次调用由兜底译码：额外记原始异常类型与 HTTP status。对外码已被
    域规则压平（权限读不出真实原因），这两项是租户可见面上唯一的补偿。**只记类型与状态码**
    —— ``AppError`` 文案可能夹内部实现细节，`aud_logs` 是租户可见面。
    """
    detail: dict = {"method": method, "durationMs": streaming.elapsed_ms(started)}
    params = payload.get("params") if isinstance(payload, dict) else None
    if isinstance(params, dict):
        if isinstance(params.get("id"), str):
            detail["taskId"] = params["id"]
        message = params.get("message")
        if isinstance(message, dict) and isinstance(message.get("contextId"), str):
            # 与 ``extract_message_context_id`` 同一口径（先 ``strip()`` 再比长度）：入口接受
            # 的「首尾带空白但 strip 后不超限」的值，服务侧会正常用作 ``conversation_id``，
            # 审计若按原样比长度就会把这条正常调用从租户可见面抹掉。超长值本就过不了下游
            # ``conversation_id`` 契约（会退化成 500），没有理由写进租户可见的 aud_logs。
            context_id = message["contextId"].strip()
            if context_id and len(context_id) <= CONVERSATION_ID_MAX_LENGTH:
                detail["contextId"] = context_id
    error = envelope.get("error") if isinstance(envelope, dict) else None
    if isinstance(error, dict):
        detail["errorCode"] = error.get("code")
    if origin is not None:
        detail["errorType"] = type(origin).__name__
        detail["errorStatus"] = origin.status_code
    return detail


async def _dispatch_a2a_rpc(
    db: AsyncSession,
    ctx: TenantContext,
    agent_id: UUID,
    payload: object,
    *,
    base_url: str,
) -> dict:
    """JSON-RPC 2.0 分发：``message/send`` + ``tasks/get`` + ``tasks/cancel``。

    协议级错误一律回 HTTP 200 + ``error`` 信封（JSON-RPC over HTTP 惯例），使对端能从
    正文读到失败原因；抛异常只会让对端拿到无正文的 500。

    ``base_url`` 由请求推导（与 Card 同源），用于把 ``Task.artifacts`` 的下载地址写成
    绝对地址。

    ``message/stream``、``tasks/resubscribe`` 不在本函数内：它们要回 SSE 而非单个 JSON，
    分别由 ``open_a2a_stream`` / ``open_task_subscription`` 处理，视图层按 ``method`` 先行分流。

    ``tasks/pushNotificationConfig/*`` 四方法见 ``push_rpc``；其余未知方法 ``METHOD_NOT_FOUND``。
    """
    req_id: object = payload.get("id") if isinstance(payload, dict) else None
    if not isinstance(payload, dict) or "method" not in payload:
        return jsonrpc_error(req_id, INVALID_REQUEST, "非法 JSON-RPC 请求")
    method = str(payload.get("method"))
    supported = {"message/send", "tasks/get", "tasks/cancel"} | set(PUSH_NOTIFICATION_METHODS)
    if method not in supported:
        return jsonrpc_error(req_id, METHOD_NOT_FOUND, f"不支持的方法: {method}")
    params = payload.get("params")
    if not isinstance(params, dict):
        return jsonrpc_error(req_id, INVALID_PARAMS, f"{method} 缺少 params")

    if method in PUSH_NOTIFICATION_METHODS:
        from miles_portal.tenant.a2a.services.push_rpc import handle_push_notification_rpc

        return await handle_push_notification_rpc(db, ctx, agent_id, method, req_id, params)
    if method == "tasks/get":
        return await _handle_tasks_get(db, ctx, agent_id, req_id, params, base_url=base_url)
    if method == "tasks/cancel":
        return await _handle_tasks_cancel(db, ctx, agent_id, req_id, params)
    return await _handle_message_send(db, ctx, agent_id, req_id, params)
