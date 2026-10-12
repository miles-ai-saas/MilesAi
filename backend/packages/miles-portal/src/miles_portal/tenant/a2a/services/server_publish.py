"""A2A Server：发布门槛与 Agent Card 组装。

经 ``server`` 门面 re-export；查删软删等依赖通过 ``server`` 模块属性解析，
以便单测 ``monkeypatch.setattr(server_svc, ...)`` 仍生效。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.exceptions import NotFoundError
from miles_core.models.agent import Agent, AgentStatus, AgentType
from miles_core.soft_delete import not_deleted
from miles_integrations.langchain.toolkit.catalog import bound_skill_ids
from miles_portal.tenant.a2a.server import A2A_PUBLISH_FLAG, build_agent_card, is_publish_enabled
from miles_portal.tenant.skills.models import SkillPackage


def is_agent_published(agent: Agent) -> bool:
    """该智能体是否对外发布为 A2A Server（config 开关 + custom + 启用）。"""
    return is_publish_enabled(agent.config) and agent.agent_type == AgentType.CUSTOM and agent.status == AgentStatus.ENABLED


async def load_published_agent(db: AsyncSession, agent_id: UUID) -> Agent:
    """按 ID 加载已发布智能体；不存在 / 未发布一律 ``NotFoundError``。

    未发布时不区分「不存在」与「未发布」：对匿名探测者暴露差异等于泄露智能体是否存在。
    """
    from miles_portal.tenant.a2a.services import server as svc

    agent = await db.get(Agent, agent_id)
    if not agent or svc.is_marked_deleted(agent) or not svc.is_agent_published(agent):
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
    from miles_portal.tenant.a2a.services import server as svc

    skills = await svc._bound_skill_entries(db, agent)
    return build_agent_card(
        agent_id=agent.id,
        name=agent.name,
        description=agent.description,
        base_url=base_url,
        skills=skills,
    )


async def build_agent_card_by_id(db: AsyncSession, agent_id: UUID, *, base_url: str) -> dict:
    """加载已发布智能体并组装 Card（API 声明层唯一入口）。"""
    from miles_portal.tenant.a2a.services import server as svc

    agent = await svc.load_published_agent(db, agent_id)
    return await svc.build_public_agent_card(db, agent, base_url=base_url)


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
