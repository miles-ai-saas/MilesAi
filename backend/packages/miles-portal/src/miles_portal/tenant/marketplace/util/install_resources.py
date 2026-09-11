"""已安装市场应用资源快照：采集与写回 KB / Flow / Agent。"""

from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.tenant import TenantContext
from miles_core.models.agent import Agent
from miles_core.models.flow import Flow
from miles_core.models.kb import KnowledgeBase
from miles_portal.tenant.agents.schemas.agent import AgentUpdate
from miles_portal.tenant.agents.services.agent import AgentService
from miles_portal.tenant.flows.schemas.flow import FlowSaveGraph, FlowUpdate
from miles_portal.tenant.flows.services.flow import FlowService
from miles_portal.tenant.kb.schemas.kb import KnowledgeBaseUpdate
from miles_portal.tenant.kb.services.kb import KnowledgeBaseService
from miles_portal.tenant.marketplace.models import AppInstall
from miles_portal.tenant.marketplace.util import load_flow_template_graph


async def capture_install_resources(
    db: AsyncSession,
    ctx: TenantContext,
    install: AppInstall,
) -> dict:
    """采集当前安装关联资源的 manifest 形态快照。"""
    resources: dict = {}
    flow_svc = FlowService(db, ctx)

    if install.kb_id:
        kb = await db.get(KnowledgeBase, install.kb_id)
        if kb:
            resources["knowledge_base"] = {
                "name": kb.name,
                "description": kb.description,
            }

    if install.flow_id:
        flow = await db.get(Flow, install.flow_id)
        graph_json = None
        if flow and flow.current_version > 0:
            version = await flow_svc.repo.get_version(flow.id, flow.current_version)
            graph_json = version.graph_json if version else None
        if flow:
            resources["flow"] = {
                "name": flow.name,
                "description": flow.description,
                "graph_json": graph_json or load_flow_template_graph("rag"),
            }

    if install.agent_id:
        agent = await db.get(Agent, install.agent_id)
        if agent:
            resources["agent"] = {
                "name": agent.name,
                "description": agent.description,
                "system_prompt": agent.system_prompt,
            }

    return resources


async def apply_resources_to_install(
    db: AsyncSession,
    ctx: TenantContext,
    install: AppInstall,
    resources: dict,
    *,
    remark: str = "市场资源同步",
) -> None:
    """将 resources 写回 install 关联的 KB / Flow / Agent。"""
    kb_svc = KnowledgeBaseService(db, ctx)
    flow_svc = FlowService(db, ctx)
    agent_svc = AgentService(db, ctx)

    kb_spec = resources.get("knowledge_base")
    if kb_spec and install.kb_id:
        await kb_svc.update_kb(
            install.kb_id,
            KnowledgeBaseUpdate(
                name=kb_spec.get("name"),
                description=kb_spec.get("description"),
            ),
        )

    flow_spec = resources.get("flow")
    if flow_spec and install.flow_id:
        graph = flow_spec.get("graph_json") or load_flow_template_graph("rag")
        await flow_svc.update_flow(
            install.flow_id,
            FlowUpdate(
                name=flow_spec.get("name"),
                description=flow_spec.get("description"),
            ),
        )
        await flow_svc.save_graph(
            install.flow_id,
            FlowSaveGraph(graph_json=graph, remark=remark),
        )

    agent_spec = resources.get("agent")
    if agent_spec and install.agent_id:
        await agent_svc.update_agent(
            install.agent_id,
            AgentUpdate(
                name=agent_spec.get("name"),
                description=agent_spec.get("description"),
                system_prompt=agent_spec.get("system_prompt"),
            ),
        )
