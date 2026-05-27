"""应用升级预览与 manifest 同步。"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.common.exceptions import BadRequestError
from app.models.agent import Agent
from app.models.flow import Flow
from app.models.kb import KnowledgeBase
from app.tenant.agents.schemas.agent import AgentUpdate
from app.tenant.agents.services.agent import AgentService
from app.tenant.flows.schemas.flow import FlowSaveGraph, FlowUpdate
from app.tenant.flows.services.flow import FlowService
from app.tenant.kb.schemas.kb import KnowledgeBaseUpdate
from app.tenant.kb.services.kb import KnowledgeBaseService
from app.tenant.marketplace.models import AppInstall, MarketplaceAppStatus
from app.tenant.marketplace.schemas.marketplace import AppUpgradePreview, AppUpgradeResult
from app.tenant.marketplace.util import load_rag_graph_template
from app.tenant.marketplace.util.upgrade_diff import (
    build_upgrade_preview,
    diff_agent,
    diff_flow,
    diff_knowledge_base,
)


def _preview_to_schema(data) -> AppUpgradePreview:
    return AppUpgradePreview.model_validate(data, from_attributes=True)


class MarketplaceUpgradeMixin:
    """升级预览与执行。"""

    async def _get_install_for_upgrade(self, app_id: UUID) -> tuple[AppInstall, object]:
        stmt = (
            select(AppInstall)
            .where(
                AppInstall.tenant_id == self.ctx.tenant_id,
                AppInstall.app_id == app_id,
            )
            .options(selectinload(AppInstall.app))
        )
        install = (await self.db.execute(stmt)).scalar_one_or_none()
        if not install:
            raise BadRequestError("未安装该应用")
        app = install.app or await self.get_app_or_raise(app_id)
        if app.status != MarketplaceAppStatus.PUBLISHED:
            raise BadRequestError("应用未发布，无法升级")
        return install, app

    async def _collect_upgrade_diffs(self, install: AppInstall, app) -> list:
        resources_manifest = (app.manifest or {}).get("resources") or app.manifest or {}
        diffs = []
        flow_svc = FlowService(self.db, self.ctx)

        kb_spec = resources_manifest.get("knowledge_base")
        if kb_spec and install.kb_id:
            kb = await self.db.get(KnowledgeBase, install.kb_id)
            diffs.append(
                diff_knowledge_base(
                    resource_id=install.kb_id,
                    current_name=kb.name if kb else None,
                    current_description=kb.description if kb else None,
                    target=kb_spec,
                )
            )

        flow_spec = resources_manifest.get("flow")
        if flow_spec and install.flow_id:
            flow = await self.db.get(Flow, install.flow_id)
            current_graph = None
            if flow and flow.current_version > 0:
                version = await flow_svc.repo.get_version(flow.id, flow.current_version)
                current_graph = version.graph_json if version else None
            diffs.append(
                diff_flow(
                    resource_id=install.flow_id,
                    current_name=flow.name if flow else None,
                    current_description=flow.description if flow else None,
                    current_graph=current_graph,
                    target=flow_spec,
                )
            )

        agent_spec = resources_manifest.get("agent")
        if agent_spec and install.agent_id:
            agent = await self.db.get(Agent, install.agent_id)
            diffs.append(
                diff_agent(
                    resource_id=install.agent_id,
                    current_name=agent.name if agent else None,
                    current_description=agent.description if agent else None,
                    current_system_prompt=agent.system_prompt if agent else None,
                    target=agent_spec,
                )
            )

        return diffs

    async def preview_upgrade(self, app_id: UUID) -> AppUpgradePreview:
        install, app = await self._get_install_for_upgrade(app_id)
        diffs = await self._collect_upgrade_diffs(install, app)
        return _preview_to_schema(
            build_upgrade_preview(
                app_id=app.id,
                app_name=app.name,
                installed_version=install.installed_version,
                target_version=app.version,
                resources=diffs,
            )
        )

    async def _apply_upgrade_resources(self, install: AppInstall, app) -> None:
        resources = (app.manifest or {}).get("resources") or app.manifest or {}
        kb_svc = KnowledgeBaseService(self.db, self.ctx)
        flow_svc = FlowService(self.db, self.ctx)
        agent_svc = AgentService(self.db, self.ctx)

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
            graph = flow_spec.get("graph_json") or load_rag_graph_template()
            await flow_svc.update_flow(
                install.flow_id,
                FlowUpdate(
                    name=flow_spec.get("name"),
                    description=flow_spec.get("description"),
                ),
            )
            await flow_svc.save_graph(
                install.flow_id,
                FlowSaveGraph(graph_json=graph, remark=f"市场升级 v{app.version}"),
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

        install.installed_version = app.version

    async def upgrade_app(self, app_id: UUID) -> AppUpgradeResult:
        install, app = await self._get_install_for_upgrade(app_id)
        if install.installed_version == app.version:
            raise BadRequestError("已是最新版本")
        prev = install.installed_version
        await self._apply_upgrade_resources(install, app)
        await self.db.flush()
        await self.db.refresh(install)
        out = self._install_out(install, app.name, app.version)
        return AppUpgradeResult(
            install=out,
            previous_version=prev,
            new_version=app.version,
            message=f"已从 v{prev} 升级到 v{app.version}",
        )
