from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError, NotFoundError
from app.core.tenant import TenantContext, assert_tenant_access, tenant_filters
from app.app_tenant.compliance.services.compliance import ComplianceService
from app.app_tenant.hooks.models import HookScope, HookTrigger
from app.app_tenant.hooks.services.runner import HookRunner
from app.langflow.runtime_factory import get_flow_runtime
from app.langflow.types import RunContext
from app.models.flow import Flow, FlowStatus, FlowVersion
from app.app_tenant.flows.repositories.flow import FlowRepository, FlowVersionRepository
from app.common.schema import PageParams, PageResult
from app.app_tenant.flows.schemas.flow import (
    FlowCreate,
    FlowOut,
    FlowRunRequest,
    FlowRunResponse,
    FlowSaveGraph,
    FlowUpdate,
    FlowVersionOut,
)
from app.core.soft_delete import is_marked_deleted, mark_deleted
from app.core.service import BaseService
from app.deletion.cascade import before_delete_flow


class FlowService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.repo = FlowRepository(db)
        self.version_repo = FlowVersionRepository(db)

    async def _get_flow_or_raise(self, flow_id: UUID) -> Flow:
        flow = await self.repo.get_by_id(flow_id)
        if not flow or is_marked_deleted(flow):
            raise NotFoundError("流程不存在")
        assert_tenant_access(self.ctx, flow.tenant_id)
        return flow

    async def list_flows(self, params: PageParams) -> PageResult[FlowOut]:
        filters = tenant_filters(self.ctx, Flow.tenant_id)
        page = await self.repo.list_page(
            page=params.page,
            size=params.size,
            filters=filters,
            order_by=Flow.created_at.desc(),
        )
        return PageResult(
            items=[FlowOut.model_validate(f) for f in page.items],
            total=page.total,
            page=page.page,
            size=page.size,
        )

    async def create_flow(self, body: FlowCreate) -> FlowOut:
        flow = await self.repo.create(
            tenant_id=self.ctx.tenant_id,
            name=body.name,
            description=body.description,
            status=FlowStatus.DRAFT,
            current_version=0,
        )
        await self.db.flush()
        await self._save_version(flow, body.graph_json, remark="初始版本")
        await self.db.refresh(flow)
        return FlowOut.model_validate(flow)

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

    async def get_flow(self, flow_id: UUID) -> FlowOut:
        flow = await self._get_flow_or_raise(flow_id)
        return FlowOut.model_validate(flow)

    async def update_flow(self, flow_id: UUID, body: FlowUpdate) -> FlowOut:
        flow = await self._get_flow_or_raise(flow_id)
        await self.repo.update_fields(flow, body.model_dump(exclude_unset=True))
        await self.db.refresh(flow)
        return FlowOut.model_validate(flow)

    async def save_graph(self, flow_id: UUID, body: FlowSaveGraph) -> FlowVersionOut:
        flow = await self._get_flow_or_raise(flow_id)
        version = await self._save_version(flow, body.graph_json, body.remark)
        return FlowVersionOut.model_validate(version)

    async def get_current_graph(self, flow_id: UUID) -> FlowVersionOut:
        flow = await self._get_flow_or_raise(flow_id)
        if flow.current_version == 0:
            raise NotFoundError("流程尚无版本")
        version = await self.repo.get_version(flow.id, flow.current_version)
        if not version:
            raise NotFoundError("流程版本不存在")
        return FlowVersionOut.model_validate(version)

    async def delete_flow(self, flow_id: UUID) -> None:
        flow = await self._get_flow_or_raise(flow_id)
        await before_delete_flow(self.db, flow.id)
        await mark_deleted(self.db, flow)

    async def publish(self, flow_id: UUID) -> FlowOut:
        flow = await self._get_flow_or_raise(flow_id)
        if flow.current_version == 0:
            raise BadRequestError("请先保存流程图")
        flow.status = FlowStatus.PUBLISHED
        await self.db.flush()
        await self.db.refresh(flow)
        return FlowOut.model_validate(flow)

    async def run(self, flow_id: UUID, body: FlowRunRequest, kb_ids: list[str] | None = None) -> FlowRunResponse:
        flow = await self._get_flow_or_raise(flow_id)
        version = await self.repo.get_version(flow.id, flow.current_version)
        if not version:
            raise BadRequestError("流程无可用版本")

        query_text = str(
            body.inputs.get("query") or body.inputs.get("message") or body.inputs.get("input") or ""
        )
        compliance = ComplianceService(self.db, self.ctx)
        hooks = HookRunner(self.db, self.ctx.tenant_id)
        hook_payload = {
            "module": "flow_run",
            "flow_id": str(flow_id),
            "inputs": body.inputs,
        }
        if query_text:
            await compliance.check_input(query_text, module="flow_run")
        await hooks.run(
            HookTrigger.BEFORE_CALL,
            HookScope.FLOW,
            flow_id,
            {**hook_payload, "direction": "in", "query": query_text},
        )

        ctx = RunContext(
            tenant_id=str(self.ctx.tenant_id),
            inputs=body.inputs,
            kb_ids=kb_ids or [],
        )
        if "query" not in ctx.inputs and body.inputs:
            ctx.inputs.setdefault("query", body.inputs.get("message", ""))
        runtime = get_flow_runtime()
        result = await runtime.run(version.graph_json, ctx)
        output = result.output
        if not isinstance(output, (str, dict, list)):
            output = str(output)
        if isinstance(output, str) and output:
            await compliance.check_output(output, module="flow_run")
        await hooks.run(
            HookTrigger.AFTER_CALL,
            HookScope.FLOW,
            flow_id,
            {**hook_payload, "direction": "out", "output": output},
        )
        return FlowRunResponse(output=output, steps=result.steps)
