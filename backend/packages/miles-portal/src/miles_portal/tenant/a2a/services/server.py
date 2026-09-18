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

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_ai.integrations.langchain.toolkit.catalog import bound_skill_ids
from miles_common.exceptions import BadRequestError, NotFoundError
from miles_common.schemas.chat_io import ChatResponse
from miles_core.logging import get_logger
from miles_core.models.agent import Agent, AgentStatus, AgentType
from miles_core.models.model.generative_job import GenerativeJob
from miles_core.soft_delete import is_marked_deleted, not_deleted
from miles_core.tenant import TenantContext
from miles_portal.tenant.a2a.server import (
    A2A_PUBLISH_FLAG,
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    TASK_NOT_CANCELABLE,
    TASK_NOT_FOUND,
    artifact_ids_from_job_result,
    build_a2a_artifacts,
    build_a2a_task,
    build_agent_card,
    extract_message_context_id,
    extract_message_text,
    is_active_generative_status,
    is_publish_enabled,
    jsonrpc_error,
    jsonrpc_result,
    to_a2a_task_state,
)
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
) -> ChatResponse:
    """入站 A2A 任务 → 平台对话链路，返回完整对话响应（含异步生成任务）。

    ``conversation_id`` 来自 A2A ``message.contextId``，作为同一会话的 ``thread_id``
    后缀恢复 LangGraph checkpoint，从而支持多轮。

    返回整个 ``ChatResponse`` 而非仅 ``answer``：产生异步生成任务时须据此回 A2A
    ``Task`` 供对端轮询。

    函数内 import ``AgentService``：``agents.services.agent`` 依赖 ``a2a`` 域内的
    peer_refs / invoke，模块级互引会成环。
    """
    from miles_portal.tenant.agents.schemas.agent import ChatRequest
    from miles_portal.tenant.agents.services.agent import AgentService

    return await AgentService(db, ctx).chat(agent_id, ChatRequest(query=text, conversation_id=conversation_id))


def _context_id_from_job_params(params: object) -> str | None:
    """从生成任务参数快照取会话标识，作为 ``Task.contextId`` 回给对端。

    委托 ``chat_artifact_sync`` 的同一解析（键约定只有一个来源），取不到则省略该字段。
    """
    from miles_portal.tenant.agents.services.chat_artifact_sync import conversation_id_from_job_params

    return conversation_id_from_job_params(params)


def _now() -> str:
    """A2A ``TaskStatus.timestamp``（ISO 8601 / UTC）。"""
    return datetime.now(UTC).isoformat()


def _first_active_job(jobs: list[dict]) -> dict | None:
    """对话响应中第一个仍在进行且带 id 的生成任务条目（终态任务无需对端轮询）。"""
    for job in jobs:
        if isinstance(job, dict) and job.get("id") and is_active_generative_status(job.get("status")):
            return job
    return None


def _agent_message(text: str, context_id: str) -> dict:
    """A2A ``Message``（agent 角色）形态；``parts`` 带 ``text`` 以兼容各家解析。

    ``contextId`` 必须回显：对端据此把后续消息接回同一上下文，否则每轮都是新对话。
    """
    return {
        "kind": "message",
        "role": "agent",
        "messageId": str(uuid4()),
        "contextId": context_id,
        "parts": [{"type": "text", "text": text}],
    }


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
                timestamp=_now(),
            ),
        )
    return jsonrpc_result(req_id, _agent_message(response.answer, context_id))


def _parse_task_id(params: dict) -> UUID:
    """取 ``tasks/*`` 的 ``params.id`` 并解析为 UUID；非法一律 ``BadRequestError``。"""
    raw = params.get("id")
    if not isinstance(raw, str) or not raw.strip():
        raise BadRequestError("tasks/* 缺少 params.id")
    try:
        return UUID(raw.strip())
    except ValueError as exc:
        raise BadRequestError("params.id 不是合法的任务 ID") from exc


async def _load_owned_agent_task(
    db: AsyncSession,
    ctx: TenantContext,
    agent_id: UUID,
    task_id: UUID,
) -> GenerativeJob:
    """取「该智能体自己发起」的生成任务；不存在或不属于它一律 ``NotFoundError``。

    必须校验归属：只按租户取数会让同租户另一个智能体的 key 也能查/取消本智能体任务，
    并据 ``task_id`` 推断其产物下载地址。回 404 而非 403 —— 不向对端确认任务是否存在。
    """
    job = await get_generative_job_for_tenant(db, ctx, task_id)
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
    否则本租户任意附件都能被取走。
    """
    job = await _load_owned_agent_task(db, ctx, agent_id, task_id)
    if str(attachment_id) not in artifact_ids_from_job_result(job.result):
        raise NotFoundError("附件不是该任务的产物")
    return await AttachmentService(db, ctx).read_attachment_bytes(attachment_id)


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
        job_id = _parse_task_id(params)
        job = await _load_owned_agent_task(db, ctx, agent_id, job_id)
    except BadRequestError as exc:
        return jsonrpc_error(req_id, INVALID_PARAMS, str(exc))
    except NotFoundError as exc:
        return jsonrpc_error(req_id, TASK_NOT_FOUND, str(exc))

    return jsonrpc_result(
        req_id,
        build_a2a_task(
            task_id=str(job.id),
            context_id=_context_id_from_job_params(job.params),
            state=to_a2a_task_state(job.status.value),
            timestamp=_now(),
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
        job_id = _parse_task_id(params)
        await _load_owned_agent_task(db, ctx, agent_id, job_id)
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
            context_id=_context_id_from_job_params(job.params),
            state=to_a2a_task_state(job.status.value),
            timestamp=_now(),
        ),
    )


async def handle_a2a_rpc(
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

    ``message/stream``、``tasks/resubscribe``、``tasks/pushNotificationConfig/*`` 未实现，
    一律 ``METHOD_NOT_FOUND``（不静默成功）。
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
