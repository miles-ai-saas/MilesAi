"""应用升级预览与 manifest 同步。

升级链路：对比已安装 KB/Flow/Agent 与 manifest → preview → 覆盖字段并更新 installed_version。
Flow 升级会 save_graph 并可选 remark；不自动重新 publish。
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from miles_common.exceptions import BadRequestError
from miles_core.models.agent import Agent
from miles_core.models.flow import Flow
from miles_core.models.kb import KnowledgeBase
from miles_portal.tenant.flows.services.flow import FlowService
from miles_portal.tenant.marketplace.models import AppInstall, MarketplaceAppStatus
from miles_portal.tenant.marketplace.schemas.marketplace import AppUpgradePreview, AppUpgradeResult
from miles_portal.tenant.marketplace.util.install_resources import apply_resources_to_install
from miles_portal.tenant.marketplace.util.upgrade_diff import (
    build_upgrade_preview,
    diff_agent,
    diff_flow,
    diff_knowledge_base,
)


def _preview_to_schema(data) -> AppUpgradePreview:
    """UpgradePreviewData dataclass → Pydantic schema。"""
    return AppUpgradePreview.model_validate(data, from_attributes=True)


class MarketplaceUpgradeMixin:
    """升级预览与执行。"""

    async def _get_install_for_upgrade(self, app_id: UUID) -> tuple[AppInstall, object]:
        """校验已安装且应用仍 published，返回 (install, app)。"""
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
        """逐资源 diff 已安装实体与市场 manifest 目标值。"""
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
        """返回升级 diff 预览（字段变更、画布节点/边数、是否可升级）。"""
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
        """将 manifest 字段写入已安装 KB/Flow/Agent，并更新 installed_version。"""
        resources = (app.manifest or {}).get("resources") or app.manifest or {}
        await apply_resources_to_install(
            self.db,
            self.ctx,
            install,
            resources,
            remark=f"市场升级 v{app.version}",
        )
        install.installed_version = app.version

    async def upgrade_app(self, app_id: UUID) -> AppUpgradeResult:
        """执行升级：应用 manifest 变更并返回版本前后信息。"""
        install, app = await self._get_install_for_upgrade(app_id)
        if install.installed_version == app.version:
            raise BadRequestError("已是最新版本")
        prev = install.installed_version
        await self._save_install_snapshot(install, version=prev)
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
