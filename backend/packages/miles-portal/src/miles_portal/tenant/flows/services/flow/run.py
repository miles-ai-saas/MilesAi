"""流程试运行、编译预览与子流程依赖。"""

from __future__ import annotations

from uuid import UUID

from miles_ai.flow_runtime.compiler import validate_graph_for_compile
from miles_ai.flow_runtime.runtime_factory import get_flow_runtime
from miles_ai.flow_runtime.subflow.validate import validate_subflow_references
from miles_ai.flow_runtime.types import RunContext
from miles_common.exceptions import BadRequestError
from miles_core.models.flow import Flow
from miles_portal.tenant.compliance.constants import SCAN_MODULE_FLOW_RUN
from miles_portal.tenant.compliance.services.compliance import ComplianceService
from miles_portal.tenant.flows.schemas.flow import FlowRunRequest, FlowRunResponse
from miles_portal.tenant.flows.services.run_context import make_flow_model_resolver
from miles_portal.tenant.generative.services.job import GenerativeJobService
from miles_portal.tenant.generative.services.job_execution import (
    submit_generative_image_job,
    submit_generative_video_job,
)
from miles_portal.tenant.hooks.models import HookScope, HookTrigger
from miles_portal.tenant.hooks.services.app_scope import resolve_install_app_id
from miles_portal.tenant.hooks.services.runner import HookRunner
from miles_portal.tenant.kb.services.embeddings import build_kb_retrieval_bindings
from miles_portal.tenant.models.services.generative_model_resolve import (
    resolve_image_gen_model,
    resolve_video_gen_model,
)
from miles_portal.tenant.models.services.usage import make_flow_usage_sink_factory


class FlowRunMixin:
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
        app_id = await resolve_install_app_id(self.db, self.ctx.tenant_id, flow_id=flow_id)
        hook_payload = {
            "module": SCAN_MODULE_FLOW_RUN,
            "flow_id": str(flow_id),
            "inputs": body.inputs,
            "media_count": len(body.media),
            "attachment_ids": [str(m.attachment_id) for m in body.media],
        }
        if app_id is not None:
            hook_payload["app_id"] = str(app_id)
        try:
            before = await hooks.run_resource(
                HookTrigger.BEFORE_CALL,
                HookScope.FLOW,
                flow_id,
                {**hook_payload, "direction": "in", "query": query_text},
                app_id=app_id,
                phase="before",
            )
            hook_payload = before.payload
            query_text = str(hook_payload.get("query", query_text))
            if query_text:
                await compliance.check_input(query_text, module=SCAN_MODULE_FLOW_RUN)
            await compliance.check_media_input(body.media, module=SCAN_MODULE_FLOW_RUN)

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
            await hooks.run_resource(
                HookTrigger.AFTER_CALL,
                HookScope.FLOW,
                flow_id,
                {**hook_payload, "direction": "out", "output": output},
                app_id=app_id,
                phase="after",
            )
            return FlowRunResponse(output=output, steps=result.steps)
        except Exception as exc:
            await hooks.run_resource(
                HookTrigger.ON_ERROR,
                HookScope.FLOW,
                flow_id,
                {**hook_payload, "error": str(exc)},
                app_id=app_id,
                phase="error",
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

