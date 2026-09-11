"""应用安装回滚：恢复最近一次升级前快照。"""

from uuid import UUID

from app.common.exceptions import BadRequestError
from app.tenant.marketplace.schemas.marketplace import (
    AppRollbackPreview,
    AppRollbackResult,
    UpgradeResourceDiff,
)
from app.tenant.marketplace.util.upgrade_diff import (
    build_upgrade_preview,
    diff_agent,
    diff_flow,
    diff_knowledge_base,
)


class MarketplaceRollbackMixin:
    """回滚预览与执行。"""

    async def preview_rollback(self, app_id: UUID) -> AppRollbackPreview:
        """回滚预览：对比当前资源与最近快照，输出各资源 diff。

        无历史快照时抛 ``BadRequestError``；仅构造差异，不落库。
        """
        install, app = await self._get_install_for_upgrade(app_id)
        snap = await self._get_latest_snapshot(install.id)
        if not snap:
            raise BadRequestError("没有可回滚的历史版本")

        diffs = []
        resources = snap.resources or {}

        kb_spec = resources.get("knowledge_base")
        if kb_spec and install.kb_id:
            from app.models.kb import KnowledgeBase

            kb = await self.db.get(KnowledgeBase, install.kb_id)
            diffs.append(
                diff_knowledge_base(
                    resource_id=install.kb_id,
                    current_name=kb.name if kb else None,
                    current_description=kb.description if kb else None,
                    target=kb_spec,
                )
            )

        flow_spec = resources.get("flow")
        if flow_spec and install.flow_id:
            from app.models.flow import Flow
            from app.tenant.flows.services.flow import FlowService

            flow = await self.db.get(Flow, install.flow_id)
            current_graph = None
            if flow and flow.current_version > 0:
                version = await FlowService(self.db, self.ctx).repo.get_version(flow.id, flow.current_version)
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

        agent_spec = resources.get("agent")
        if agent_spec and install.agent_id:
            from app.models.agent import Agent

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

        preview = build_upgrade_preview(
            app_id=app.id,
            app_name=app.name,
            installed_version=install.installed_version,
            target_version=snap.version,
            resources=diffs,
        )
        resource_models = [UpgradeResourceDiff.model_validate(r, from_attributes=True) for r in preview.resources]
        return AppRollbackPreview(
            app_id=preview.app_id,
            app_name=preview.app_name,
            current_version=install.installed_version,
            target_version=snap.version,
            can_rollback=True,
            resources=resource_models,
            message=preview.message or f"将回滚到 v{snap.version}",
        )

    async def rollback_app(self, app_id: UUID) -> AppRollbackResult:
        """执行回滚：恢复最近快照并刷新安装记录，返回前后版本信息。"""
        install, app = await self._get_install_for_upgrade(app_id)
        prev = install.installed_version
        snap = await self._restore_latest_snapshot(install)
        await self.db.refresh(install)
        out = self._install_out(install, app.name, app.version)
        return AppRollbackResult(
            install=out,
            previous_version=prev,
            restored_version=snap.version,
            message=f"已从 v{prev} 回滚到 v{snap.version}",
        )
