"""A2A Server 用例层：发布门槛、Card 组装、JSON-RPC 分发（``message/send`` / ``tasks/*``）。

Card 与信封的纯逻辑在 ``tenant.a2a.server``；本模块只做 DB 读取与对话路由，供
``miles_openapi.views.a2a_server``（API 声明层，不得直接 import ORM）调用。

鉴权边界
--------
Card 是公开发现元数据（A2A 约定，且 ``card_client.fetch_agent_card`` 不带凭证），故
Card GET 无鉴权，仅由 ``config.a2a_publish`` 门槛约束可见性；调用端点 ``message/send``
必须带该智能体的 ``X-API-Key``（复用 ``require_agent_api_key``）。
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_ai.integrations.langchain.chat_models import OnDelta
from miles_ai.integrations.langchain.toolkit.catalog import bound_skill_ids
from miles_common.exceptions import AppError, BadRequestError, ForbiddenError, NotFoundError
from miles_common.schemas.chat_io import CONVERSATION_ID_MAX_LENGTH, ChatResponse
from miles_core.infra.db import AsyncSessionLocal
from miles_core.logging import get_logger
from miles_core.models.agent import Agent, AgentStatus, AgentType
from miles_core.models.model.generative_job import GenerativeJob
from miles_core.soft_delete import is_marked_deleted, not_deleted
from miles_core.tenant import TenantContext
from miles_portal.tenant.a2a.server import (
    A2A_PUBLISH_FLAG,
    AUDIT_ACTION_ARTIFACT_DOWNLOAD,
    AUDIT_ACTION_MESSAGE_SEND,
    AUDIT_ACTION_MESSAGE_STREAM,
    AUDIT_ACTION_TASKS_CANCEL,
    AUDIT_ACTION_TASKS_GET,
    AUDIT_OUTCOME_CANCELED,
    AUDIT_OUTCOME_FAILED,
    AUDIT_OUTCOME_OK,
    AUDIT_OUTCOME_REJECTED,
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    TASK_NOT_CANCELABLE,
    TASK_NOT_FOUND,
    TASK_STATE_COMPLETED,
    TASK_STATE_FAILED,
    TASK_STATE_REJECTED,
    TASK_STATE_WORKING,
    app_error_envelope,
    artifact_ids_from_job_result,
    build_a2a_agent_message,
    build_a2a_artifacts,
    build_a2a_status_update,
    build_a2a_task,
    build_agent_card,
    extract_message_context_id,
    extract_message_text,
    is_active_generative_status,
    is_publish_enabled,
    jsonrpc_error,
    jsonrpc_result,
    now_iso,
    to_a2a_task_state,
)
from miles_portal.tenant.a2a.services import streaming
from miles_portal.tenant.a2a.services.audit import schedule_audit, write_a2a_audit
from miles_portal.tenant.attachments.services.attachment import AttachmentService
from miles_portal.tenant.generative.services.job import GenerativeJobService
from miles_portal.tenant.generative.services.job_execution import get_generative_job_for_tenant
from miles_portal.tenant.skills.models import SkillPackage

logger = get_logger(__name__)


def is_agent_published(agent: Agent) -> bool:
    """该智能体是否对外发布为 A2A Server（config 开关 + custom + 启用）。"""
    return is_publish_enabled(agent.config) and agent.agent_type == AgentType.CUSTOM and agent.status == AgentStatus.ENABLED


async def load_published_agent(db: AsyncSession, agent_id: UUID) -> Agent:
    """按 ID 加载已发布智能体；不存在 / 未发布一律 ``NotFoundError``。

    未发布时不区分「不存在」与「未发布」：对匿名探测者暴露差异等于泄露智能体是否存在。
    """
    agent = await db.get(Agent, agent_id)
    if not agent or is_marked_deleted(agent) or not is_agent_published(agent):
        raise NotFoundError("A2A Server 不存在或未发布")
    return agent


async def _bound_skill_entries(db: AsyncSession, agent: Agent) -> list[dict]:
    """把绑定技能包映射为 Card ``skills``（无绑定返回空列表，由 Card 组装回退）。"""
    ids = bound_skill_ids(agent.config)
    if not ids:
        return []
    parsed: list[UUID] = []
    for raw in ids:
        try:
            parsed.append(UUID(raw))
        except ValueError:
            # 静默可接受：config 中非 UUID 的绑定项无法查库，跳过；合法项照常展示。
            continue
    if not parsed:
        return []
    rows = (
        await db.execute(
            select(SkillPackage).where(
                SkillPackage.tenant_id == agent.tenant_id,
                SkillPackage.id.in_(parsed),
                SkillPackage.is_active.is_(True),
                not_deleted(SkillPackage),
            )
        )
    ).scalars()
    return [
        {
            "id": f"skill:{row.slug}",
            "name": row.name,
            "description": row.description or "",
            "tags": [],
        }
        for row in rows
    ]


async def build_public_agent_card(db: AsyncSession, agent: Agent, *, base_url: str) -> dict:
    """按绑定数据组装 Agent Card（``base_url`` 取自请求，见 ``server.build_agent_card``）。"""
    skills = await _bound_skill_entries(db, agent)
    return build_agent_card(
        agent_id=agent.id,
        name=agent.name,
        description=agent.description,
        base_url=base_url,
        skills=skills,
    )


async def build_agent_card_by_id(db: AsyncSession, agent_id: UUID, *, base_url: str) -> dict:
    """加载已发布智能体并组装 Card（API 声明层唯一入口）。"""
    agent = await load_published_agent(db, agent_id)
    return await build_public_agent_card(db, agent, base_url=base_url)


async def resolve_default_published_agent_id(db: AsyncSession) -> UUID | None:
    """根路径别名：全平台唯一发布时返回其 ID，否则 ``None``。

    多租户下根路径无租户上下文，命中多个时静默取第一个会把 A 租户的 Card 发给 B 的
    对端，故不猜。部署方可改用按智能体路径（Card ``url`` 已声明）。
    """
    rows = (
        await db.execute(
            select(Agent.id).where(
                Agent.agent_type == AgentType.CUSTOM,
                Agent.status == AgentStatus.ENABLED,
                not_deleted(Agent),
                Agent.config[A2A_PUBLISH_FLAG].astext == "true",
            )
        )
    ).scalars()
    ids = list(rows)
    return ids[0] if len(ids) == 1 else None


async def run_published_agent_chat(
    db: AsyncSession,
    ctx: TenantContext,
    agent_id: UUID,
    text: str,
    *,
    conversation_id: str | None = None,
    on_delta: OnDelta | None = None,
) -> ChatResponse:
    """入站 A2A 任务 → 平台对话链路，返回完整对话响应（含异步生成任务）。

    ``conversation_id`` 来自 A2A ``message.contextId``，作为同一会话的 ``thread_id``
    后缀恢复 LangGraph checkpoint，从而支持多轮。

    ``on_delta`` 为真流回调（``message/stream`` 用）：逐 token 交给调用方下发；不传则
    只在返回时一次性拿到完整回答（``message/send`` 与不支持真流的路由都走这条）。

    返回整个 ``ChatResponse`` 而非仅 ``answer``：产生异步生成任务时须据此回 A2A
    ``Task`` 供对端轮询。

    函数内 import ``AgentService``：``agents.services.agent`` 依赖 ``a2a`` 域内的
    peer_refs / invoke，模块级互引会成环。
    """
    from miles_portal.tenant.agents.schemas.agent import ChatRequest
    from miles_portal.tenant.agents.services.agent import AgentService

    return await AgentService(db, ctx).chat(agent_id, ChatRequest(query=text, conversation_id=conversation_id), on_delta=on_delta)


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
        text = extract_message_text(params)
        # 未带 contextId 时生成一个并回显：对端才有可复用的上下文标识，多轮才接得上。
        context_id = extract_message_context_id(params) or str(uuid4())
    except (NotFoundError, BadRequestError) as exc:
        return jsonrpc_error(req_id, INVALID_PARAMS, str(exc))

    try:
        response = await run_published_agent_chat(db, ctx, agent_id, text, conversation_id=context_id)
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


def parse_task_id(params: dict) -> UUID:
    """取 ``tasks/*`` 的 ``params.id`` 并解析为 UUID；非法一律 ``BadRequestError``。"""
    raw = params.get("id")
    if not isinstance(raw, str) or not raw.strip():
        raise BadRequestError("tasks/* 缺少 params.id")
    try:
        return UUID(raw.strip())
    except ValueError as exc:
        raise BadRequestError("params.id 不是合法的任务 ID") from exc


async def load_owned_agent_task(
    db: AsyncSession,
    ctx: TenantContext,
    agent_id: UUID,
    task_id: UUID,
) -> GenerativeJob:
    """取「该智能体自己发起」的生成任务；不存在或不属于它一律 ``NotFoundError``。

    必须校验归属：只按租户取数会让同租户另一个智能体的 key 也能查/取消本智能体任务，
    并据 ``task_id`` 推断其产物下载地址。回 404 而非 403 —— 不向对端确认任务是否存在。

    外租户 id 由下层 ``get_generative_job_for_tenant`` 的 ``ForbiddenError`` 表达，此处
    一并归一为 ``NotFoundError``：A2A 对外面不接受以 403 区分「存在但越权」与「不存在」。
    """
    try:
        job = await get_generative_job_for_tenant(db, ctx, task_id)
    except ForbiddenError:
        # 外租户 id：下层 ``assert_tenant_access`` 抛 403。若让它逸出，对端会拿到平台信封的
        # HTTP 403 —— 既破坏本端点「协议级错误一律回 JSON-RPC 信封」的契约（对端无从把错误
        # 对回自己的 ``id``），又让 403 与 ``-32001`` 可区分，等于给出探测「该任务是否存在于
        # 别的租户」的 oracle。故与「不属于本智能体」同口径归一；文案固定，不回显内部措辞。
        raise NotFoundError("生成任务不存在") from None
    if job.source_ref_type != "agent" or job.source_ref_id != agent_id:
        raise NotFoundError("生成任务不存在")
    return job


async def read_task_artifact(
    db: AsyncSession,
    ctx: TenantContext,
    agent_id: UUID,
    task_id: UUID,
    attachment_id: UUID,
) -> tuple[bytes, str, str]:
    """下载某任务产物，返回 ``(data, mime_type, filename)``。

    授权精确到「该智能体 · 该任务 · 该产物」：先验任务归属，再验附件确为该任务产物，
    否则本租户任意附件都能被取走。成败都留一条审计流水（「谁把产物取走了」要查得到）。
    """
    started = time.monotonic()
    try:
        job = await load_owned_agent_task(db, ctx, agent_id, task_id)
        if str(attachment_id) not in artifact_ids_from_job_result(job.result):
            raise NotFoundError("附件不是该任务的产物")
        data, mime, filename = await AttachmentService(db, ctx).read_attachment_bytes(attachment_id)
    except NotFoundError:
        await write_a2a_audit(
            ctx=ctx,
            agent_id=agent_id,
            action=AUDIT_ACTION_ARTIFACT_DOWNLOAD,
            outcome=AUDIT_OUTCOME_FAILED,
            detail={"taskId": str(task_id), "errorCode": TASK_NOT_FOUND, "durationMs": streaming.elapsed_ms(started)},
        )
        raise
    await write_a2a_audit(
        ctx=ctx,
        agent_id=agent_id,
        action=AUDIT_ACTION_ARTIFACT_DOWNLOAD,
        outcome=AUDIT_OUTCOME_OK,
        detail={"taskId": str(task_id), "durationMs": streaming.elapsed_ms(started)},
    )
    return data, mime, filename


async def _handle_tasks_get(
    db: AsyncSession,
    ctx: TenantContext,
    agent_id: UUID,
    req_id: object,
    params: dict,
    *,
    base_url: str,
) -> dict:
    """``tasks/get``：查生成任务状态，成功时附产物下载地址。

    只读查询走 ORM 取数（不经 ``GenerativeJobService.get_job``，后者会回写会话
    artifacts —— 对外查询不应带写副作用）。
    """
    try:
        job_id = parse_task_id(params)
        job = await load_owned_agent_task(db, ctx, agent_id, job_id)
    except BadRequestError as exc:
        return jsonrpc_error(req_id, INVALID_PARAMS, str(exc))
    except NotFoundError as exc:
        return jsonrpc_error(req_id, TASK_NOT_FOUND, str(exc))

    return jsonrpc_result(
        req_id,
        build_a2a_task(
            task_id=str(job.id),
            context_id=context_id_from_job_params(job.params),
            state=to_a2a_task_state(job.status.value),
            timestamp=now_iso(),
            artifacts=build_a2a_artifacts(job_result=job.result, agent_id=agent_id, task_id=job.id, base_url=base_url),
        ),
    )


async def _handle_tasks_cancel(
    db: AsyncSession,
    ctx: TenantContext,
    agent_id: UUID,
    req_id: object,
    params: dict,
) -> dict:
    """``tasks/cancel``：取消未结束的生成任务；已结束回 ``TASK_NOT_CANCELABLE``。"""
    try:
        job_id = parse_task_id(params)
        await load_owned_agent_task(db, ctx, agent_id, job_id)
    except BadRequestError as exc:
        return jsonrpc_error(req_id, INVALID_PARAMS, str(exc))
    except NotFoundError as exc:
        return jsonrpc_error(req_id, TASK_NOT_FOUND, str(exc))

    try:
        job = await GenerativeJobService(db, ctx).cancel_job(job_id)
    except BadRequestError as exc:
        return jsonrpc_error(req_id, TASK_NOT_CANCELABLE, str(exc))

    return jsonrpc_result(
        req_id,
        build_a2a_task(
            task_id=str(job.id),
            context_id=context_id_from_job_params(job.params),
            state=to_a2a_task_state(job.status.value),
            timestamp=now_iso(),
        ),
    )


#: JSON-RPC 方法 → 租户审计 ``action``。``message/stream`` 不在此表：它的 outcome 只有
#: 终态帧才知道，由 ``_stream_turn`` 自己写。不支持的方法没有对应动作名，不编造流水。
_AUDIT_ACTION_BY_METHOD = {
    "message/send": AUDIT_ACTION_MESSAGE_SEND,
    "tasks/get": AUDIT_ACTION_TASKS_GET,
    "tasks/cancel": AUDIT_ACTION_TASKS_CANCEL,
}

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

    ``tasks/pushNotificationConfig/get`` 等未实现方法一律 ``METHOD_NOT_FOUND``（不静默成功）。
    """
    req_id: object = payload.get("id") if isinstance(payload, dict) else None
    if not isinstance(payload, dict) or "method" not in payload:
        return jsonrpc_error(req_id, INVALID_REQUEST, "非法 JSON-RPC 请求")
    method = str(payload.get("method"))
    if method not in {"message/send", "tasks/get", "tasks/cancel"}:
        return jsonrpc_error(req_id, METHOD_NOT_FOUND, f"不支持的方法: {method}")
    params = payload.get("params")
    if not isinstance(params, dict):
        return jsonrpc_error(req_id, INVALID_PARAMS, f"{method} 缺少 params")

    if method == "tasks/get":
        return await _handle_tasks_get(db, ctx, agent_id, req_id, params, base_url=base_url)
    if method == "tasks/cancel":
        return await _handle_tasks_cancel(db, ctx, agent_id, req_id, params)
    return await _handle_message_send(db, ctx, agent_id, req_id, params)


#: SSE 帧之间的增量队列上限。满时 ``on_delta`` 会等待消费者 —— 对上游形成背压，
#: 否则慢消费者 + 长回答会把队列撑成无界缓冲。
STREAM_QUEUE_MAXSIZE = 64

#: 与「产出一片空串」区分的收尾哨兵。
_STREAM_DONE = object()


async def _audit_stream_preflight(ctx: TenantContext, agent_id: UUID, error_code: int, started: float) -> None:
    """``message/stream`` 前置失败的审计：与 send 侧**可达的**参数类失败对称（缺 ``params`` /
    未发布智能体 / 非法 ``contextId`` 等）。send 侧对「无/未知 method」是不写流水的（没有
    action 名可记），而那两个分支从视图不可达，故不在此列。

    不记就出现「同一个非法调用，``message/send`` 有迹、``message/stream`` 零痕迹」，
    探测式调用可以不留痕迹。口径用 ``failed`` 与 ``message/send`` 对齐（``_rpc_audit_outcome``
    只看信封有没有 ``error``）—— ``rejected`` 专指智能体/合规拒绝处理，不是协议级错误。
    """
    await write_a2a_audit(
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
    started = time.monotonic()
    req_id: object = payload.get("id") if isinstance(payload, dict) else None
    if not isinstance(payload, dict) or "method" not in payload:
        await _audit_stream_preflight(ctx, agent_id, INVALID_REQUEST, started)
        return jsonrpc_error(req_id, INVALID_REQUEST, "非法 JSON-RPC 请求")
    params = payload.get("params")
    if not isinstance(params, dict):
        await _audit_stream_preflight(ctx, agent_id, INVALID_PARAMS, started)
        return jsonrpc_error(req_id, INVALID_PARAMS, "message/stream 缺少 params")
    try:
        await load_published_agent(db, agent_id)
        text = extract_message_text(params)
        # 未带 contextId 时生成一个：首轮就得用它，否则第一轮 checkpoint 落在别的
        # thread，对端第二轮带上该 id 时模型并无上一轮记忆。
        context_id = extract_message_context_id(params) or str(uuid4())
    except (NotFoundError, BadRequestError) as exc:
        await _audit_stream_preflight(ctx, agent_id, INVALID_PARAMS, started)
        return jsonrpc_error(req_id, INVALID_PARAMS, str(exc))
    # 结束请求级事务并归还连接：``yield`` 依赖的 teardown 要等整条响应发完才跑，而流可能
    # 持续数分钟，不主动结束就会有一条连接陪跑（轮次自身还会另开一条）。
    # 用 ``commit`` 而非 ``rollback``：同一会话里鉴权依赖已 ``flush`` 了 API Key 的
    # ``last_used_at``（``touch_last_used`` 的契约就是「由调用方决定提交」），rollback 会把
    # 这笔记账丢掉，让流式调用在「密钥最后使用时间」上永远不更新。
    await db.commit()
    return _stream_turn(ctx, agent_id, req_id, text, context_id)


async def _stream_turn(
    ctx: TenantContext,
    agent_id: UUID,
    req_id: object,
    text: str,
    context_id: str,
) -> AsyncIterator[str]:
    """跑一轮对话并以 SSE 帧下发：首帧 Task、中间帧增量、末帧终态。"""
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
            write_a2a_audit(
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
            async with AsyncSessionLocal() as turn_db:
                try:
                    outcome["response"] = await run_published_agent_chat(turn_db, ctx, agent_id, text, conversation_id=context_id, on_delta=on_delta)
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
        job = _first_active_job(response.generative_jobs)
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


def _failure_text(error: Exception) -> str:
    """失败终态给对端的可读原因：``BadRequestError`` 的 message 本就可读，其余统一前缀。"""
    if isinstance(error, BadRequestError):
        return error.message
    return f"智能体执行失败: {error}"
