"""流程版本：保存画布、历史、恢复与发布。"""

from __future__ import annotations

import copy
from uuid import UUID

from miles_common.exceptions import BadRequestError, NotFoundError
from miles_core.models.flow import Flow, FlowStatus, FlowVersion
from miles_core.models.meta.tag import TagEntityType
from miles_portal.tenant.flows.schemas.flow import (
    FlowOut,
    FlowRestoreVersion,
    FlowSaveGraph,
    FlowVersionOut,
    FlowVersionSummaryOut,
)
from miles_portal.tenant.tags.services.tag import TagService


class FlowVersionsMixin:
    async def _save_version(self, flow: Flow, graph_json: dict, remark: str | None = None) -> FlowVersion:
        new_version = flow.current_version + 1
        version = await self.version_repo.create(
            flow_id=flow.id,
            version=new_version,
            graph_json=graph_json,
            editor_id=self.ctx.user_id,
            remark=remark,
        )
        flow.current_version = new_version
        await self.db.flush()
        return version

    async def save_graph(self, flow_id: UUID, body: FlowSaveGraph) -> FlowVersionOut:
        """每次保存递增版本号并更新 flow.current_version。"""
        flow = await self._get_flow_or_raise(flow_id)
        version = await self._save_version(flow, body.graph_json, body.remark)
        return FlowVersionOut.model_validate(version)

    async def get_current_graph(self, flow_id: UUID) -> FlowVersionOut:
        """返回当前版本画布；尚无版本或版本缺失时抛 ``NotFoundError``。"""
        flow = await self._get_flow_or_raise(flow_id)
        if flow.current_version == 0:
            raise NotFoundError("流程尚无版本")
        version = await self.repo.get_version(flow.id, flow.current_version)
        if not version:
            raise NotFoundError("流程版本不存在")
        return FlowVersionOut.model_validate(version)

    async def list_versions(self, flow_id: UUID) -> list[FlowVersionSummaryOut]:
        """返回流程的版本摘要列表。"""
        flow = await self._get_flow_or_raise(flow_id)
        versions = await self.repo.list_versions(flow.id)
        return [FlowVersionSummaryOut.model_validate(v) for v in versions]

    async def get_version_graph(self, flow_id: UUID, version: int) -> FlowVersionOut:
        """按版本号返回画布；版本不存在时抛 ``NotFoundError``。"""
        flow = await self._get_flow_or_raise(flow_id)
        row = await self.repo.get_version(flow.id, version)
        if not row:
            raise NotFoundError("流程版本不存在")
        return FlowVersionOut.model_validate(row)

    async def restore_version(
        self,
        flow_id: UUID,
        version: int,
        body: FlowRestoreVersion | None = None,
    ) -> FlowVersionOut:
        """从历史版本拷贝 ``graph_json`` 另存为新版本（对齐市场回滚：不改指针、不删历史）。"""
        body = body or FlowRestoreVersion()
        flow = await self._get_flow_or_raise(flow_id)
        if version == flow.current_version:
            raise BadRequestError("所选已是当前版本，无需恢复")
        row = await self.repo.get_version(flow.id, version)
        if not row:
            raise NotFoundError("流程版本不存在")
        remark = (body.remark or "").strip() or f"恢复自 v{version}"
        new_ver = await self._save_version(flow, copy.deepcopy(row.graph_json), remark)
        if body.publish and flow.status != FlowStatus.PUBLISHED:
            if flow.current_version == 0:
                raise BadRequestError("请先保存流程图")
            flow.status = FlowStatus.PUBLISHED
            await self.db.flush()
        return FlowVersionOut.model_validate(new_ver)

    async def publish(self, flow_id: UUID) -> FlowOut:
        """发布流程；尚未保存任何版本时拒绝。"""
        flow = await self._get_flow_or_raise(flow_id)
        if flow.current_version == 0:
            raise BadRequestError("请先保存流程图")
        flow.status = FlowStatus.PUBLISHED
        await self.db.flush()
        await self.db.refresh(flow)
        tags_map = await TagService(self.db, self.ctx).get_refs_map(TagEntityType.FLOW, {flow.id})
        return self._to_out(flow, tags_map.get(flow.id, []))

