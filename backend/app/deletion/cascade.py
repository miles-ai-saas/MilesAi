"""
逻辑外键场景下的级联删除 / 引用解除（无 DB 物理外键）。

删 KB 时
--------
``KnowledgeBaseService.delete_kb`` 先逐文档 ``delete_document``（清分片/向量/OSS），
再 ``before_delete_kb`` 解绑 ``agt_kb_bindings`` 与市场 ``AppInstall.kb_id``，最后软删 KB 行。

删 Agent/Flow 时同理，避免工作台与市场出现悬空引用。
"""

from uuid import UUID

from sqlalchemy import and_, delete, update

from app.core.soft_delete import mark_deleted_where, not_deleted
from sqlalchemy.ext.asyncio import AsyncSession

from app.tenant.hooks.models import HookBinding, HookScope
from app.models.marketplace import AppInstall
from app.models.agent import Agent, AgentSubAgentBinding, agent_kb_bindings
from app.models.agent.chat_call import AgentChatCall
from app.models.agent.chat_session import AgentChatMessage, AgentChatSession
from app.models.agent.schedule import AgentSchedule
from app.models.flow import FlowVersion


async def unlink_sub_agent_bindings(
    db: AsyncSession,
    *,
    parent_agent_id: UUID | None = None,
    child_agent_id: UUID | None = None,
) -> None:
    """删除父子智能体绑定行（删 Agent 前调用）。"""
    if parent_agent_id is None and child_agent_id is None:
        return
    stmt = delete(AgentSubAgentBinding)
    if parent_agent_id is not None:
        stmt = stmt.where(AgentSubAgentBinding.parent_agent_id == parent_agent_id)
    if child_agent_id is not None:
        stmt = stmt.where(AgentSubAgentBinding.child_agent_id == child_agent_id)
    await db.execute(stmt)


async def unlink_agent_kb_bindings(
    db: AsyncSession,
    *,
    agent_id: UUID | None = None,
    kb_id: UUID | None = None,
) -> None:
    """解除 agent_kb_bindings 关联表记录。"""
    if agent_id is None and kb_id is None:
        return
    stmt = delete(agent_kb_bindings)
    if agent_id is not None:
        stmt = stmt.where(agent_kb_bindings.c.agent_id == agent_id)
    if kb_id is not None:
        stmt = stmt.where(agent_kb_bindings.c.kb_id == kb_id)
    await db.execute(stmt)


async def nullify_app_install_refs(
    db: AsyncSession,
    *,
    agent_id: UUID | None = None,
    flow_id: UUID | None = None,
    kb_id: UUID | None = None,
) -> None:
    """市场安装记录置空对已删资源的引用。"""
    if agent_id is None and flow_id is None and kb_id is None:
        return
    values: dict = {}
    if agent_id is not None:
        values["agent_id"] = None
    if flow_id is not None:
        values["flow_id"] = None
    if kb_id is not None:
        values["kb_id"] = None

    conditions = []
    if agent_id is not None:
        conditions.append(AppInstall.agent_id == agent_id)
    if flow_id is not None:
        conditions.append(AppInstall.flow_id == flow_id)
    if kb_id is not None:
        conditions.append(AppInstall.kb_id == kb_id)
    stmt = update(AppInstall).where(and_(*conditions)).values(**values)
    await db.execute(stmt)


async def clear_agents_published_flow_ref(db: AsyncSession, flow_id: UUID) -> None:
    """删流程前清空智能体 published_flow_id 指针。"""
    await db.execute(update(Agent).where(Agent.published_flow_id == flow_id).values(published_flow_id=None))


async def delete_hook_bindings_for_target(
    db: AsyncSession,
    scope: HookScope,
    target_id: UUID,
) -> None:
    """软删指定 scope/target 的 Hook 绑定。"""
    await mark_deleted_where(
        db,
        HookBinding,
        HookBinding.scope == scope,
        HookBinding.target_id == target_id,
        not_deleted(HookBinding),
    )


async def delete_flow_versions(db: AsyncSession, flow_id: UUID) -> None:
    """软删流程下所有版本行。"""
    await mark_deleted_where(db, FlowVersion, FlowVersion.flow_id == flow_id)


async def before_delete_agent(db: AsyncSession, agent_id: UUID) -> None:
    """删智能体前：子 Agent 绑定、KB 绑定、市场引用、Hook、定时任务。"""
    await unlink_sub_agent_bindings(db, parent_agent_id=agent_id, child_agent_id=agent_id)
    await unlink_agent_kb_bindings(db, agent_id=agent_id)
    await nullify_app_install_refs(db, agent_id=agent_id)
    await delete_hook_bindings_for_target(db, HookScope.AGENT, agent_id)
    await mark_deleted_where(
        db,
        AgentSchedule,
        AgentSchedule.agent_id == agent_id,
        not_deleted(AgentSchedule),
    )
    await db.execute(delete(AgentChatCall).where(AgentChatCall.agent_id == agent_id))
    await db.execute(delete(AgentChatMessage).where(AgentChatMessage.agent_id == agent_id))
    await db.execute(delete(AgentChatSession).where(AgentChatSession.agent_id == agent_id))


async def before_delete_kb(db: AsyncSession, kb_id: UUID) -> None:
    """删库前：文档衍生数据由 delete_document 逐条清理；此处解绑 Agent 与市场引用。"""
    await unlink_agent_kb_bindings(db, kb_id=kb_id)
    await nullify_app_install_refs(db, kb_id=kb_id)


async def before_delete_flow(db: AsyncSession, flow_id: UUID) -> None:
    """删流程前：解绑 Agent 发布指针、市场引用、Hook、版本。"""
    await clear_agents_published_flow_ref(db, flow_id)
    await nullify_app_install_refs(db, flow_id=flow_id)
    await delete_hook_bindings_for_target(db, HookScope.FLOW, flow_id)
    await delete_flow_versions(db, flow_id)
