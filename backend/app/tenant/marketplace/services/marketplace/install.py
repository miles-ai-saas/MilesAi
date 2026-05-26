"""应用安装与安装记录。"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.common.exceptions import BadRequestError, ConflictError
from app.common.schema import PageParams, PageResult
from app.core.tenant import tenant_filters
from app.tenant.agents.schemas.agent import AgentCreate
from app.tenant.agents.services.agent import AgentService
from app.tenant.flows.schemas.flow import FlowCreate
from app.tenant.flows.services.flow import FlowService
from app.tenant.kb.schemas.kb import KnowledgeBaseCreate
from app.tenant.kb.services.kb import KnowledgeBaseService
from app.tenant.marketplace.models import AppInstall, MarketplaceAppStatus
from app.tenant.marketplace.schemas.marketplace import AppInstallOut, AppInstallResult
from app.tenant.marketplace.util import load_rag_graph_template


class MarketplaceInstallMixin:
    """已发布应用安装到租户与安装记录。"""
    async def install_app(self, app_id: UUID) -> AppInstallResult:
        """将已发布应用快照复制到当前租户（KB、流程、智能体等）。"""
        app = await self.get_app_or_raise(app_id)
        if app.status != MarketplaceAppStatus.PUBLISHED:
            raise BadRequestError("应用未发布，无法安装")

        existing = await self.db.scalar(
            select(AppInstall).where(
                AppInstall.tenant_id == self.ctx.tenant_id,
                AppInstall.app_id == app_id,
            )
        )
        if existing:
            raise ConflictError("该应用已安装，可在「我的安装」中查看")

        manifest = app.manifest or {}
        resources = manifest.get("resources") or manifest
        flow_id: UUID | None = None
        agent_id: UUID | None = None
        kb_id: UUID | None = None

        kb_svc = KnowledgeBaseService(self.db, self.ctx)
        flow_svc = FlowService(self.db, self.ctx)
        agent_svc = AgentService(self.db, self.ctx)

        kb_spec = resources.get("knowledge_base")
        if kb_spec:
            kb = await kb_svc.create_kb(
                KnowledgeBaseCreate(
                    name=kb_spec.get("name", f"{app.name} 知识库"),
                    description=kb_spec.get("description", f"来自应用市场：{app.name}"),
                )
            )
            kb_id = kb.id

        flow_spec = resources.get("flow")
        if flow_spec:
            graph = flow_spec.get("graph_json") or load_rag_graph_template()
            flow = await flow_svc.create_flow(
                FlowCreate(
                    name=flow_spec.get("name", f"{app.name} 流程"),
                    description=flow_spec.get("description"),
                    graph_json=graph,
                )
            )
            flow_id = flow.id
            if flow_spec.get("auto_publish", True):
                await flow_svc.publish(flow_id)

        agent_spec = resources.get("agent")
        if agent_spec:
            bind_kb = agent_spec.get("bind_kb", True) and kb_id is not None
            bind_flow = agent_spec.get("bind_flow", True) and flow_id is not None
            agent = await agent_svc.create_agent(
                AgentCreate(
                    name=agent_spec.get("name", f"{app.name} 助手"),
                    description=agent_spec.get("description", app.description),
                    system_prompt=agent_spec.get(
                        "system_prompt",
                        "你是企业知识库助手，请基于检索内容准确回答用户问题。",
                    ),
                    published_flow_id=flow_id if bind_flow else None,
                    kb_ids=[kb_id] if bind_kb else [],
                    config=agent_spec.get("config") or {},
                )
            )
            agent_id = agent.id

        if not any([flow_id, agent_id, kb_id]):
            raise BadRequestError("应用模板未定义可安装资源（flow/agent/knowledge_base）")

        install = AppInstall(
            tenant_id=self.ctx.tenant_id,
            app_id=app.id,
            installed_by=self.ctx.user_id,
            flow_id=flow_id,
            agent_id=agent_id,
            kb_id=kb_id,
        )
        self.db.add(install)
        app.install_count += 1
        await self.db.flush()
        await self.db.refresh(install)

        install_out = AppInstallOut(
            id=install.id,
            app_id=app.id,
            app_name=app.name,
            tenant_id=install.tenant_id,
            flow_id=flow_id,
            agent_id=agent_id,
            kb_id=kb_id,
            created_at=install.created_at,
        )
        return AppInstallResult(
            install=install_out,
            flow_id=flow_id,
            agent_id=agent_id,
            kb_id=kb_id,
            message="安装成功，已创建关联资源",
        )

    async def list_installs(self, params: PageParams) -> PageResult[AppInstallOut]:
        """分页列出本租户安装记录。"""
        filters = tenant_filters(self.ctx, AppInstall.tenant_id)
        stmt = (
            select(AppInstall)
            .where(*filters)
            .options(selectinload(AppInstall.app))
            .order_by(AppInstall.created_at.desc())
        )
        count_stmt = select(func.count(AppInstall.id)).where(*filters)
        total = await self.db.scalar(count_stmt)
        stmt = stmt.offset((params.page - 1) * params.size).limit(params.size)
        rows = (await self.db.execute(stmt)).scalars().all()
        items = [
            AppInstallOut(
                id=r.id,
                app_id=r.app_id,
                app_name=r.app.name if r.app else "",
                tenant_id=r.tenant_id,
                flow_id=r.flow_id,
                agent_id=r.agent_id,
                kb_id=r.kb_id,
                created_at=r.created_at,
            )
            for r in rows
        ]
        return PageResult(items=items, total=total or 0, page=params.page, size=params.size)
