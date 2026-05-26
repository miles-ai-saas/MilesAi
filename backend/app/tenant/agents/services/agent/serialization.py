"""智能体 API 输出序列化与 RAG 路由辅助判断。"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from app.models.agent import Agent, AgentType
from app.tenant.a2a.services.host_bindings import list_host_peer_bindings
from app.tenant.a2a.services.peer_refs import list_all_agent_a2a_peer_refs
from app.tenant.agents.schemas.agent import (
    A2aPeerRefOut,
    AgentOut,
    SubAgentRefOut,
)

if TYPE_CHECKING:
    from app.tenant.agents.services.agent.service import AgentService


def should_use_skill_tools_with_kb(agent: Agent, kb_ids: list[str]) -> bool:
    """绑定 KB 且开启 tool calling 时走 tool_agent（技能包和/或生图生视频工具）。"""
    cfg = agent.config if isinstance(agent.config, dict) else {}
    return bool(
        kb_ids
        and agent.model_config_id
        and cfg.get("enable_tool_calling")
        and (cfg.get("skill_package_id") or cfg.get("enable_generative_tools"))
    )


def _sub_agents_out(agent: Agent) -> list[SubAgentRefOut]:
    """从 ORM 子智能体绑定构建 ``SubAgentRefOut`` 列表（按 ``sort_order`` 排序）。"""
    refs: list[SubAgentRefOut] = []
    for b in sorted(agent.sub_agent_bindings or [], key=lambda x: x.sort_order):
        child = b.child_agent
        if not child:
            continue
        refs.append(
            SubAgentRefOut(
                id=child.id,
                name=child.name,
                role_hint=b.role_hint,
                status=child.status,
                description=child.description,
            )
        )
    return refs


def _a2a_peers_out_from_rows(refs: list) -> list[A2aPeerRefOut]:
    """将 A2A peer 关联行序列化为 ``A2aPeerRefOut``。"""
    out: list[A2aPeerRefOut] = []
    for ref in refs:
        peer = ref.peer
        if not peer:
            continue
        kws = ref.trigger_keywords if isinstance(ref.trigger_keywords, list) else []
        out.append(
            A2aPeerRefOut(
                id=peer.id,
                name=peer.name,
                role_hint=ref.role_hint,
                trigger_keywords=[str(k) for k in kws],
                enabled=ref.enabled,
                status=peer.status.value,
                card_display_name=peer.card_display_name,
                agent_card_url=peer.agent_card_url,
            )
        )
    return out


def _bindings_to_a2a_out(bindings: list) -> list[A2aPeerRefOut]:
    """Host 模式 peer 绑定列表 → API 输出（与 ``_a2a_peers_out_from_rows`` 同形）。"""
    return _a2a_peers_out_from_rows(bindings)


async def agent_out(
    svc: AgentService,
    agent: Agent,
    *,
    category_names: dict[UUID, str] | None = None,
    tag_refs: list | None = None,
) -> AgentOut:
    """组装 ``AgentOut``（含分类名、标签、KB、子 Agent、A2A peer）。"""
    if agent.agent_type == AgentType.A2A:
        bindings = await list_host_peer_bindings(svc.db, agent.id)
        a2a_out = _bindings_to_a2a_out(bindings)
    else:
        refs = await list_all_agent_a2a_peer_refs(svc.db, agent.id)
        a2a_out = _a2a_peers_out_from_rows(refs)
    cat_name = None
    if agent.category_id and category_names:
        cat_name = category_names.get(agent.category_id)
    return AgentOut(
        id=agent.id,
        tenant_id=agent.tenant_id,
        agent_type=agent.agent_type,
        category_id=agent.category_id,
        category_name=cat_name,
        tags=tag_refs or [],
        name=agent.name,
        description=agent.description,
        status=agent.status,
        system_prompt=agent.system_prompt,
        prompt_template_id=agent.prompt_template_id,
        model_config_id=agent.model_config_id,
        published_flow_id=agent.published_flow_id,
        kb_ids=[kb.id for kb in agent.knowledge_bases],
        sub_agents=_sub_agents_out(agent),
        a2a_peers=a2a_out,
        config=agent.config or {},
        created_at=agent.created_at,
    )
