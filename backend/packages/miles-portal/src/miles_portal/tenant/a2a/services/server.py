"""A2A Server 用例层：发布门槛、Card 组装、JSON-RPC ``message/send`` 分发。

Card 与信封的纯逻辑在 ``tenant.a2a.server``；本模块只做 DB 读取与对话路由，供
``miles_openapi.views.a2a_server``（API 声明层，不得直接 import ORM）调用。

鉴权边界
--------
Card 是公开发现元数据（A2A 约定，且 ``card_client.fetch_agent_card`` 不带凭证），故
Card GET 无鉴权，仅由 ``config.a2a_publish`` 门槛约束可见性；调用端点 ``message/send``
必须带该智能体的 ``X-API-Key``（复用 ``require_agent_api_key``）。
"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_ai.integrations.langchain.toolkit.catalog import bound_skill_ids
from miles_common.exceptions import BadRequestError, NotFoundError
from miles_core.logging import get_logger
from miles_core.models.agent import Agent, AgentStatus, AgentType
from miles_core.soft_delete import is_marked_deleted, not_deleted
from miles_core.tenant import TenantContext
from miles_portal.tenant.a2a.server import (
    A2A_PUBLISH_FLAG,
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    build_agent_card,
    extract_message_text,
    is_publish_enabled,
    jsonrpc_error,
    jsonrpc_result,
)
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
) -> str:
    """入站 A2A 任务 → 平台对话链路，返回回答正文。

    函数内 import ``AgentService``：``agents.services.agent`` 依赖 ``a2a`` 域内的
    peer_refs / invoke，模块级互引会成环。
    """
    from miles_portal.tenant.agents.schemas.agent import ChatRequest
    from miles_portal.tenant.agents.services.agent import AgentService

    response = await AgentService(db, ctx).chat(agent_id, ChatRequest(query=text))
    return response.answer


def _agent_message(text: str) -> dict:
    """A2A ``Message``（agent 角色）形态；``parts`` 带 ``text`` 以兼容各家解析。"""
    return {
        "kind": "message",
        "role": "agent",
        "messageId": str(uuid4()),
        "parts": [{"type": "text", "text": text}],
    }


async def handle_a2a_rpc(
    db: AsyncSession,
    ctx: TenantContext,
    agent_id: UUID,
    payload: object,
) -> dict:
    """JSON-RPC 2.0 分发：目前仅支持 ``message/send``（``capabilities.streaming=false``）。

    协议级错误一律回 HTTP 200 + ``error`` 信封（JSON-RPC over HTTP 惯例），使对端能从
    正文读到失败原因；抛异常只会让对端拿到无正文的 500。
    """
    req_id: object = payload.get("id") if isinstance(payload, dict) else None
    if not isinstance(payload, dict) or "method" not in payload:
        return jsonrpc_error(req_id, INVALID_REQUEST, "非法 JSON-RPC 请求")
    method = str(payload.get("method"))
    if method != "message/send":
        return jsonrpc_error(req_id, METHOD_NOT_FOUND, f"不支持的方法: {method}")
    params = payload.get("params")
    if not isinstance(params, dict):
        return jsonrpc_error(req_id, INVALID_PARAMS, "message/send 缺少 params")

    try:
        await load_published_agent(db, agent_id)
        text = extract_message_text(params)
    except (NotFoundError, BadRequestError) as exc:
        return jsonrpc_error(req_id, INVALID_PARAMS, str(exc))

    try:
        answer = await run_published_agent_chat(db, ctx, agent_id, text)
    except Exception as exc:
        # 对端只拿到 JSON-RPC 错误信封；本平台侧必须留栈，否则线上无法定位。
        logger.exception("A2A message/send 执行失败: agent_id=%s", agent_id)
        return jsonrpc_error(req_id, INTERNAL_ERROR, f"智能体执行失败: {exc}")

    return jsonrpc_result(req_id, _agent_message(answer))
