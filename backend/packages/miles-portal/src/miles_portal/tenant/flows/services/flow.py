"""
流程 L1：版本化 graph_json、发布、试运行与 LangGraph 编译预览。

与知识库
--------
``run(..., kb_ids=...)`` 将 id 列表注入 ``RunContext``，画布 **KnowledgeSearch** 在未配置
节点级 ``kb_id`` 时使用该列表（与 Agent 发布流程对话行为一致）。

智能体绑定 ``published_flow_id`` 后由 ``AgentService.chat`` 构造 ``RunContext`` 并执行，
不经过本 Service 的调试 API。
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from miles_ai.flow_runtime.compiler import validate_graph_for_compile
from miles_ai.flow_runtime.runtime_factory import get_flow_runtime
from miles_ai.flow_runtime.subflow.validate import validate_subflow_references
from miles_ai.flow_runtime.templates.registry import list_flow_templates
from miles_ai.flow_runtime.types import RunContext
from miles_common.exceptions import BadRequestError, NotFoundError
from miles_common.schema import PageParams, PageResult
from miles_core.models.flow import Flow, FlowStatus, FlowVersion
from miles_core.models.meta.tag import TagEntityType
from miles_core.service import BaseService
from miles_core.soft_delete import is_marked_deleted, mark_deleted
from miles_core.tenant import TenantContext, assert_tenant_access, tenant_filters
from miles_portal.deletion.cascade import before_delete_flow
from miles_portal.tenant.compliance.constants import SCAN_MODULE_FLOW_RUN
from miles_portal.tenant.compliance.services.compliance import ComplianceService
from miles_portal.tenant.flows.meta import flow_meta_dict
from miles_portal.tenant.flows.repositories.flow import FlowRepository, FlowVersionRepository
from miles_portal.tenant.flows.schemas.flow import (
    FlowCreate,
    FlowOut,
    FlowRunRequest,
    FlowRunResponse,
    FlowSaveGraph,
    FlowUpdate,
    FlowVersionOut,
    FlowVersionSummaryOut,
)
from miles_portal.tenant.flows.schemas.meta import FlowMetaOut
from miles_portal.tenant.flows.schemas.template import FlowTemplateOut, FlowTemplatesOut
from miles_portal.tenant.flows.services.run_context import make_flow_model_resolver
from miles_portal.tenant.generative.services.job import GenerativeJobService
from miles_portal.tenant.generative.services.job_execution import (
    submit_generative_image_job,
    submit_generative_video_job,
)
from miles_portal.tenant.hooks.models import HookScope, HookTrigger
from miles_portal.tenant.hooks.services.runner import HookRunner
from miles_portal.tenant.kb.services.embeddings import build_kb_retrieval_bindings
from miles_portal.tenant.models.services.generative_model_resolve import (
    resolve_image_gen_model,
    resolve_video_gen_model,
)
from miles_portal.tenant.models.services.usage import make_flow_usage_sink_factory
from miles_portal.tenant.tags.schemas.tag import TagRefOut
from miles_portal.tenant.tags.services.tag import TagService


class FlowService(BaseService):
    """保存画布即新版本；智能体绑定 published_flow_id 后由 AgentService 执行。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.repo = FlowRepository(db)
        self.version_repo = FlowVersionRepository(db)

    async def get_meta(self) -> FlowMetaOut:
        """返回枚举展示字典（无 DB 查询，文案来自 tenant/*/meta.py）。"""
        return FlowMetaOut.model_validate(flow_meta_dict())

    async def list_templates(self) -> FlowTemplatesOut:
        """返回内置画布模板（含 graph_json，无 DB 查询）。"""
        items = [FlowTemplateOut.model_validate(row) for row in list_flow_templates()]
        return FlowTemplatesOut(items=items)

    async def _get_flow_or_raise(self, flow_id: UUID) -> Flow:
        flow = await self.repo.get_by_id(flow_id)
        if not flow or is_marked_deleted(flow):
            raise NotFoundError("流程不存在")
        assert_tenant_access(self.ctx, flow.tenant_id)
        return flow

    def _to_out(self, row: Flow, tags: list[TagRefOut] | None = None) -> FlowOut:
        return FlowOut(
            id=row.id,
            tenant_id=row.tenant_id,
            name=row.name,
            description=row.description,
            tags=tags or [],
            status=row.status,
            current_version=row.current_version,
            created_at=row.created_at,
        )

    async def list_flows(
        self,
        params: PageParams,
        *,
        tag_ids: list[UUID] | None = None,
    ) -> PageResult[FlowOut]:
        """分页列出流程，可按标签筛选，并批量补全标签引用。"""
        filters = tenant_filters(self.ctx, Flow.tenant_id)
        tag_subq = TagService(self.db, self.ctx).entity_id_filter(TagEntityType.FLOW, tag_ids or [])
        if tag_subq is not None:
            filters.append(Flow.id.in_(tag_subq))
        page = await self.repo.list_page(
            page=params.page,
            size=params.size,
            filters=filters,
            order_by=Flow.created_at.desc(),
        )
        tags_map = await TagService(self.db, self.ctx).get_refs_map(TagEntityType.FLOW, {f.id for f in page.items})
        return PageResult(
            items=[self._to_out(f, tags_map.get(f.id, [])) for f in page.items],
            total=page.total,
            page=page.page,
            size=page.size,
        )

    async def create_flow(self, body: FlowCreate) -> FlowOut:
        """创建流程并写入初始版本；受租户流程数配额约束。"""
        from miles_portal.tenant.system.services.quota import assert_can_create_flow

        await assert_can_create_flow(self.db, self.ctx.tenant_id)
        flow = await self.repo.create(
            tenant_id=self.ctx.tenant_id,
            name=body.name,
            description=body.description,
            status=FlowStatus.DRAFT,
            current_version=0,
        )
        await self.db.flush()
        if body.tag_ids:
            await TagService(self.db, self.ctx).replace_entity_tags(TagEntityType.FLOW, flow.id, body.tag_ids)
        await self._save_version(flow, body.graph_json, remark="初始版本")
        await self.db.refresh(flow)
        tags_map = await TagService(self.db, self.ctx).get_refs_map(TagEntityType.FLOW, {flow.id})
        return self._to_out(flow, tags_map.get(flow.id, []))

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
        """返回流程详情并附标签。"""
        flow = await self._get_flow_or_raise(flow_id)
        tags_map = await TagService(self.db, self.ctx).get_refs_map(TagEntityType.FLOW, {flow.id})
        return self._to_out(flow, tags_map.get(flow.id, []))

    async def update_flow(self, flow_id: UUID, body: FlowUpdate) -> FlowOut:
        """更新流程元信息与标签（标签为全量替换）。"""
        flow = await self._get_flow_or_raise(flow_id)
        data = body.model_dump(exclude_unset=True)
        tag_ids = data.pop("tag_ids", None)
        await self.repo.update_fields(flow, data)
        await self.db.flush()
        if tag_ids is not None:
            await TagService(self.db, self.ctx).replace_entity_tags(TagEntityType.FLOW, flow.id, tag_ids)
        await self.db.refresh(flow)
        tags_map = await TagService(self.db, self.ctx).get_refs_map(TagEntityType.FLOW, {flow.id})
        return self._to_out(flow, tags_map.get(flow.id, []))

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

    async def delete_flow(self, flow_id: UUID) -> None:
        """软删除流程：先清标签与级联依赖，再打删除标记。"""
        flow = await self._get_flow_or_raise(flow_id)
        await TagService(self.db, self.ctx).clear_entity_tags(TagEntityType.FLOW, flow.id)
        await before_delete_flow(self.db, flow.id)
        await mark_deleted(self.db, flow)

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

    async def run(self, flow_id: UUID, body: FlowRunRequest) -> FlowRunResponse:
        """
        工作台调试运行：合规 + Hook + ``get_flow_runtime().run``。

        ``body.kb_ids`` 用于测试带 KnowledgeSearch 节点的画布。
        """
        from miles_portal.tenant.attachments.services.media_reader import build_flow_media_reader
        from miles_portal.tenant.compliance.services.scan_words_loader import build_scan_words_loader
        from miles_portal.tenant.flows.services.subflow_loader import build_subflow_graph_loader
        from miles_portal.tenant.generative.services.orchestration import (
            generate_image_for_model,
            generate_video_for_model,
        )
        from miles_portal.tenant.prompts.services.template_loader import build_prompt_template_loader
        from miles_portal.tenant.tools.services.flow_invoker import build_flow_tool_invoker

        flow = await self._get_flow_or_raise(flow_id)
        version = await self.repo.get_version(flow.id, flow.current_version)
        if not version:
            raise BadRequestError("流程无可用版本")

        query_text = str(body.inputs.get("query") or body.inputs.get("message") or body.inputs.get("input") or "").strip()
        if not query_text and body.media:
            query_text = "[附图]"
        compliance = ComplianceService(self.db, self.ctx)
        hooks = HookRunner(self.db, self.ctx.tenant_id)
        hook_payload = {
            "module": SCAN_MODULE_FLOW_RUN,
            "flow_id": str(flow_id),
            "inputs": body.inputs,
            "media_count": len(body.media),
            "attachment_ids": [str(m.attachment_id) for m in body.media],
        }
        try:
            before = await hooks.run(
                HookTrigger.BEFORE_CALL,
                HookScope.FLOW,
                flow_id,
                {**hook_payload, "direction": "in", "query": query_text},
            )
            hook_payload = before.payload
            query_text = str(hook_payload.get("query", query_text))
            if query_text:
                await compliance.check_input(query_text, module=SCAN_MODULE_FLOW_RUN)

            run_inputs = dict(body.inputs)
            if query_text:
                run_inputs["query"] = query_text
            hook_payload["inputs"] = run_inputs

            ctx = RunContext(
                tenant_id=str(self.ctx.tenant_id),
                inputs=run_inputs,
                kb_ids=[str(k) for k in body.kb_ids],
                user_id=str(self.ctx.user_id),
                permissions=self.ctx.permissions,
                is_superuser=self.ctx.is_superuser,
                media=[m.model_dump(mode="json") for m in body.media],
                generative_video_async=body.async_generative,
                generative_image_async=body.async_generative,
                current_flow_id=str(flow_id),
                subflow_depth=0,
                resolve_model=make_flow_model_resolver(self.ctx.tenant_id),
                usage_sink_factory=make_flow_usage_sink_factory(self.ctx.tenant_id, source_id=flow.id),
                kb_retrieval=build_kb_retrieval_bindings(),
                resolve_generative_image=resolve_image_gen_model,
                resolve_generative_video=resolve_video_gen_model,
                # settings generative_*_async 关闭时不注入 ⇒ 节点落同步 resolver 兜底（不产生生成任务）
                submit_generative_image=submit_generative_image_job if GenerativeJobService.image_async_enabled() else None,
                submit_generative_video=submit_generative_video_job if GenerativeJobService.video_async_enabled() else None,
                invoke_platform_tool=build_flow_tool_invoker(),
                resolve_prompt_template=build_prompt_template_loader(),
                load_scan_words=build_scan_words_loader(),
                load_subflow_graph=build_subflow_graph_loader(),
                media_reader=build_flow_media_reader(tenant_id=str(self.ctx.tenant_id), user_id=self.ctx.user_id),
                generate_image_sync=generate_image_for_model,
                generate_video_sync=generate_video_for_model,
            )
            if "query" not in ctx.inputs and run_inputs:
                ctx.inputs.setdefault("query", run_inputs.get("message", ""))
            result = await get_flow_runtime().run(version.graph_json, ctx)
            output = result.output
            if not isinstance(output, (str, dict, list)):
                output = str(output)
            if isinstance(output, str) and output:
                await compliance.check_output(output, module=SCAN_MODULE_FLOW_RUN)
            await hooks.run(
                HookTrigger.AFTER_CALL,
                HookScope.FLOW,
                flow_id,
                {**hook_payload, "direction": "out", "output": output},
            )
            return FlowRunResponse(output=output, steps=result.steps)
        except Exception as exc:
            await hooks.run(
                HookTrigger.ON_ERROR,
                HookScope.FLOW,
                flow_id,
                {**hook_payload, "error": str(exc)},
            )
            raise

    async def _compile_report_for_flow(self, flow: Flow) -> dict:
        version = await self.repo.get_version(flow.id, flow.current_version)
        if not version:
            raise BadRequestError("流程无可用版本")
        report = validate_graph_for_compile(version.graph_json)
        sub_errors = await validate_subflow_references(
            self.repo,
            version.graph_json,
            tenant_id=self.ctx.tenant_id,
            current_flow_id=flow.id,
        )
        if sub_errors:
            from miles_ai.flow_runtime.compiler import FlowCompileReport, _error_to_str

            merged_details = list(report.error_details) + sub_errors
            merged_errors = report.errors + [_error_to_str(e) for e in sub_errors]
            report = FlowCompileReport(
                compilable=False,
                engine=report.engine,
                node_order=report.node_order,
                node_types=report.node_types,
                execution_layers=report.execution_layers,
                parallel_groups=report.parallel_groups,
                conditional_nodes=report.conditional_nodes,
                errors=merged_errors,
                error_details=merged_details,
            )
        return report.to_dict()

    async def subflow_deps(self, flow_id: UUID) -> dict:
        """返回当前流程直接引用的子流程 ID 列表。"""
        flow = await self._get_flow_or_raise(flow_id)
        version = await self.repo.get_version(flow.id, flow.current_version)
        if not version:
            return {"flow_id": str(flow_id), "depends_on": [], "depended_by": []}
        from miles_ai.flow_runtime.subflow.resolve import iter_subflow_nodes

        depends_on: list[str] = []
        for _nid, data in iter_subflow_nodes(version.graph_json or {}):
            raw = data.get("sub_flow_id")
            if raw:
                depends_on.append(str(raw))
        return {
            "flow_id": str(flow_id),
            "depends_on": sorted(set(depends_on)),
            "depended_by": [],
        }

    async def compile_preview(self, flow_id: UUID) -> dict:
        """
        校验当前版本 ``graph_json`` 能否被 LangGraph 编译（不执行）。

        返回 ``FlowCompileReport.to_dict()``：``compilable``、``errors``、``execution_layers`` 等。
        """
        flow = await self._get_flow_or_raise(flow_id)
        return await self._compile_report_for_flow(flow)
