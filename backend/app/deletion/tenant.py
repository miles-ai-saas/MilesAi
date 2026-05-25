"""租户级数据清空（运营停用/删租户时调用）。

注意：此处为物理硬删除，用于租户彻底清库；日常 API 删除走软删除（deleted_at）。
"""

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tenant.audit_log.models import TenantAuditLog
from app.tenant.compliance.models import InterceptLog, SensitiveWord
from app.tenant.hooks.models import HookBinding, HookDefinition
from app.tenant.marketplace.models import AppInstall
from app.tenant.mcp.models import McpRunnerSession, McpService
from app.tenant.prompts.models import PromptTemplate
from app.tenant.skills.models import SkillPackage
from app.tenant.skills.storage import remove_tenant_skills
from app.tenant.tools.models import Tool, ToolInvocationLog
from app.infra.storage import delete_object
from app.deletion.cascade import (
    before_delete_agent,
    before_delete_flow,
    before_delete_kb,
)
from app.deletion.document import clear_document_derived_data_async
from app.models.agent import Agent
from app.models.model import ModelConfig
from app.models.flow import Flow
from app.models.kb import Document, KnowledgeBase
from app.models.role import Role, role_permissions, user_roles
from app.models.task import CeleryTaskRecord
from app.models.user import User


async def purge_tenant_data(db: AsyncSession, tenant_id: UUID) -> None:
    """硬删租户下 KB/文档/OSS、Agent、Flow 及附属表（不删 tenants 行本身）。

    顺序：文档衍生数据 → before_delete_kb → Agent/Flow 级联 → 审计/市场/合规等。
    运营 AdminTenantService 停用/删租户前调用；日常 API 用软删除。
    """
    kb_ids = list(
        (await db.execute(select(KnowledgeBase.id).where(KnowledgeBase.tenant_id == tenant_id)))
        .scalars()
        .all()
    )
    for kb_id in kb_ids:
        doc_rows = (
            await db.execute(
                select(Document.id, Document.object_key, Document.object_bucket).where(
                    Document.kb_id == kb_id
                )
            )
        ).all()
        for doc_id, object_key, object_bucket in doc_rows:
            await clear_document_derived_data_async(db, doc_id)
            if object_key and object_key != "pending":
                delete_object(object_key, object_bucket)
            doc = await db.get(Document, doc_id)
            if doc:
                await db.delete(doc)
        await before_delete_kb(db, kb_id)
        kb = await db.get(KnowledgeBase, kb_id)
        if kb:
            await db.delete(kb)

    agent_ids = list(
        (await db.execute(select(Agent.id).where(Agent.tenant_id == tenant_id))).scalars().all()
    )
    for agent_id in agent_ids:
        await before_delete_agent(db, agent_id)
        agent = await db.get(Agent, agent_id)
        if agent:
            await db.delete(agent)

    flow_ids = list(
        (await db.execute(select(Flow.id).where(Flow.tenant_id == tenant_id))).scalars().all()
    )
    for flow_id in flow_ids:
        await before_delete_flow(db, flow_id)
        flow = await db.get(Flow, flow_id)
        if flow:
            await db.delete(flow)

    # sys_categories 为全平台全局字典，删除租户时不删分类行
    await db.execute(delete(TenantAuditLog).where(TenantAuditLog.tenant_id == tenant_id))
    await db.execute(delete(AppInstall).where(AppInstall.tenant_id == tenant_id))
    await db.execute(delete(HookBinding).where(HookBinding.tenant_id == tenant_id))
    await db.execute(delete(HookDefinition).where(HookDefinition.tenant_id == tenant_id))
    await db.execute(delete(PromptTemplate).where(PromptTemplate.tenant_id == tenant_id))
    await db.execute(delete(SkillPackage).where(SkillPackage.tenant_id == tenant_id))
    remove_tenant_skills(tenant_id)
    await db.execute(delete(SensitiveWord).where(SensitiveWord.tenant_id == tenant_id))
    await db.execute(delete(InterceptLog).where(InterceptLog.tenant_id == tenant_id))
    await db.execute(delete(ToolInvocationLog).where(ToolInvocationLog.tenant_id == tenant_id))
    await db.execute(delete(Tool).where(Tool.tenant_id == tenant_id))
    await db.execute(delete(McpRunnerSession).where(McpRunnerSession.tenant_id == tenant_id))
    await db.execute(delete(McpService).where(McpService.tenant_id == tenant_id))
    await db.execute(delete(CeleryTaskRecord).where(CeleryTaskRecord.tenant_id == tenant_id))
    await db.execute(delete(ModelConfig).where(ModelConfig.tenant_id == tenant_id))

    user_ids = list(
        (await db.execute(select(User.id).where(User.tenant_id == tenant_id))).scalars().all()
    )
    if user_ids:
        await db.execute(delete(user_roles).where(user_roles.c.user_id.in_(user_ids)))
        for uid in user_ids:
            user = await db.get(User, uid)
            if user:
                await db.delete(user)

    role_ids = list(
        (await db.execute(select(Role.id).where(Role.tenant_id == tenant_id))).scalars().all()
    )
    if role_ids:
        await db.execute(delete(role_permissions).where(role_permissions.c.role_id.in_(role_ids)))
        await db.execute(delete(Role).where(Role.id.in_(role_ids)))
