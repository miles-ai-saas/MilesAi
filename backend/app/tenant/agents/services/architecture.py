"""智能体执行架构视图：路由判定与 AgentService.chat 保持一致。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import NotFoundError
from app.core.service import BaseService
from app.core.soft_delete import is_marked_deleted
from app.core.tenant import TenantContext, assert_tenant_access
from app.integrations.langgraph.runner import should_use_langgraph_rag
from app.models.agent import Agent, AgentType
from app.tenant.agents.repositories.agent import AgentRepository
from app.tenant.agents.schemas.architecture import (
    PRIMARY_PATH_LABELS,
    AgentArchitectureOut,
    ArchitectureA2aPeerRef,
    ArchitectureAttachments,
    ArchitectureDecisionStep,
    ArchitectureFlowRef,
    ArchitectureKbRef,
    ArchitectureModelRef,
    ArchitectureSubAgentRef,
    PrimaryPath,
)
from app.tenant.a2a.services.peer_refs import list_agent_a2a_peer_refs
from app.tenant.agents.services.sub_agents import list_sub_agent_bindings
from app.tenant.flows.repositories.flow import FlowRepository


def _flow_is_runnable(agent: Agent) -> tuple[bool, int]:
    """与 chat 一致：published_flow_id + current_version > 0 且版本存在。"""
    if not agent.published_flow_id:
        return False, 0
    flow = agent.published_flow
    if not flow or is_marked_deleted(flow):
        return False, 0
    if flow.current_version <= 0:
        return False, 0
    return True, flow.current_version


async def _load_flow_graph(
    flow_repo: FlowRepository,
    flow_id: UUID,
    version: int,
) -> dict | None:
    row = await flow_repo.get_version(flow_id, version)
    if not row:
        return None
    return row.graph_json if isinstance(row.graph_json, dict) else None


def _resolve_primary_path(
    agent: Agent,
    *,
    has_bindings: bool,
    has_peer_refs: bool,
    flow_runnable: bool,
) -> PrimaryPath:
    if agent.agent_type == AgentType.A2A:
        return "a2a_host"
    if has_bindings:
        return "subagent_orchestration"
    if has_peer_refs:
        return "a2a_augmented"
    if flow_runnable:
        return "flow"

    kb_ids = [str(kb.id) for kb in agent.knowledge_bases or []]
    cfg = agent.config or {}
    if not kb_ids:
        if cfg.get("enable_tool_calling") and agent.model_config_id:
            return "tool_calling"
        return "direct"

    if agent.model_config_id and agent.model_config:
        if should_use_langgraph_rag(agent, kb_ids=kb_ids):
            return "rag_graph"
        return "rag_legacy"
    return "rag_retrieve_only"


def _build_decision_steps(
    agent: Agent,
    *,
    has_bindings: bool,
    has_peer_refs: bool,
    flow_runnable: bool,
    primary: PrimaryPath,
) -> list[ArchitectureDecisionStep]:
    kb_count = len(agent.knowledge_bases or [])
    steps: list[ArchitectureDecisionStep] = [
        ArchitectureDecisionStep(
            id="entry",
            label="对话入口",
            description="合规与钩子之后进入路由",
            active=False,
        ),
        ArchitectureDecisionStep(
            id="a2a_host",
            label="A2A 宿主",
            description="agent_type = a2a",
            active=primary == "a2a_host",
        ),
        ArchitectureDecisionStep(
            id="subagent",
            label="内部协同",
            description="已绑定子智能体",
            active=primary == "subagent_orchestration",
        ),
        ArchitectureDecisionStep(
            id="a2a_augmented",
            label="A2A 增强",
            description="无子智能体、已配置 A2A Peer",
            active=primary == "a2a_augmented",
        ),
        ArchitectureDecisionStep(
            id="flow",
            label="编排流程",
            description="已发布流程版本可执行",
            active=primary == "flow",
        ),
    ]

    if primary in ("tool_calling", "direct"):
        steps.append(
            ArchitectureDecisionStep(
                id="no_kb",
                label="无知识库",
                description="工具调用或直连大模型",
                active=True,
            )
        )
    elif primary in ("rag_graph", "rag_legacy", "rag_retrieve_only"):
        rag_desc = {
            "rag_graph": f"已绑定 {kb_count} 个知识库 · LangGraph",
            "rag_legacy": f"已绑定 {kb_count} 个知识库 · 线性 RAG",
            "rag_retrieve_only": f"已绑定 {kb_count} 个知识库 · 未配置大模型",
        }[primary]
        steps.append(
            ArchitectureDecisionStep(
                id="rag",
                label="知识库增强",
                description=rag_desc,
                active=True,
            )
        )
    else:
        steps.append(
            ArchitectureDecisionStep(
                id="rag_fallback",
                label="知识库 / 直连",
                description="未命中上游分支时的默认路径",
                active=False,
            )
        )

    # 标记未命中但相关的分支（便于 UI 灰显理解）
    if agent.agent_type != AgentType.A2A and primary != "a2a_host":
        pass
    if not has_bindings and primary != "subagent_orchestration":
        for s in steps:
            if s.id == "subagent" and not s.active:
                s.description = (s.description or "") + "（未配置）"
    if not has_peer_refs and primary != "a2a_augmented":
        for s in steps:
            if s.id == "a2a_augmented" and not s.active:
                s.description = (s.description or "") + "（未配置）"
    if not flow_runnable and primary != "flow":
        for s in steps:
            if s.id == "flow" and not s.active:
                s.description = (s.description or "") + "（未绑定或未发布）"

    return steps


class AgentArchitectureService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self._repo = AgentRepository(db)
        self._flow_repo = FlowRepository(db)

    async def overview(self, agent_id: UUID) -> AgentArchitectureOut:
        agent = await self._repo.get_detail(agent_id)
        if not agent or is_marked_deleted(agent):
            raise NotFoundError("智能体不存在")
        assert_tenant_access(self.ctx, agent.tenant_id)

        bindings = await list_sub_agent_bindings(self.db, agent_id)
        peer_refs = await list_agent_a2a_peer_refs(self.db, agent_id)
        has_bindings = len(bindings) > 0
        has_peer_refs = len(peer_refs) > 0
        flow_runnable, flow_version = _flow_is_runnable(agent)

        primary = _resolve_primary_path(
            agent,
            has_bindings=has_bindings,
            has_peer_refs=has_peer_refs,
            flow_runnable=flow_runnable,
        )

        attachments = ArchitectureAttachments(
            model=(
                ArchitectureModelRef(id=str(agent.model_config.id), name=agent.model_config.name)
                if agent.model_config
                else None
            ),
            kbs=[
                ArchitectureKbRef(id=str(kb.id), name=kb.name)
                for kb in (agent.knowledge_bases or [])
            ],
            sub_agents=[
                ArchitectureSubAgentRef(
                    id=str(b.child_agent_id),
                    name=(b.child_agent.name if b.child_agent else str(b.child_agent_id)),
                    role_hint=b.role_hint,
                )
                for b in bindings
            ],
            a2a_peers=[
                ArchitectureA2aPeerRef(
                    id=str(ref.peer_id),
                    name=ref.peer.name if ref.peer else str(ref.peer_id),
                    role_hint=ref.role_hint,
                    enabled=ref.enabled,
                )
                for ref in peer_refs
            ],
        )

        flow_graph: dict | None = None
        if agent.published_flow_id and agent.published_flow and not is_marked_deleted(agent.published_flow):
            flow = agent.published_flow
            attachments.flow = ArchitectureFlowRef(
                id=str(flow.id),
                name=flow.name,
                version=flow_version if flow_version > 0 else flow.current_version,
                status=flow.status.value if hasattr(flow.status, "value") else str(flow.status),
                is_runtime_path=primary == "flow",
            )
            ver = flow_version if flow_version > 0 else flow.current_version
            if ver > 0:
                flow_graph = await _load_flow_graph(self._flow_repo, flow.id, ver)

        return AgentArchitectureOut(
            agent_id=str(agent_id),
            primary_path=primary,
            primary_path_label=PRIMARY_PATH_LABELS[primary],
            decision_steps=_build_decision_steps(
                agent,
                has_bindings=has_bindings,
                has_peer_refs=has_peer_refs,
                flow_runnable=flow_runnable,
                primary=primary,
            ),
            attachments=attachments,
            flow_graph=flow_graph,
        )
