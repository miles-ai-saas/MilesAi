"""子流程 graph 解析与 RunContext 构造。

SubFlow / LoopNode 共用：``resolve_subflow_graph`` 按 published/pinned 加载子图；
``build_child_context`` 处理 input_mapping 与 subflow_depth 递增。

子图加载经 ``FlowRepoLike`` 契约（L1 ``build_subflow_graph_loader`` 注入短会话仓储）。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.common.exceptions import BadRequestError, NotFoundError
from app.core.soft_delete import is_marked_deleted
from app.flow_runtime.constants import CanvasNodeType
from app.flow_runtime.subflow.contracts import FlowRepoLike
from app.flow_runtime.types import RunContext
from app.models.flow import FlowStatus

VERSION_POLICY_PUBLISHED = "published"
VERSION_POLICY_PINNED = "pinned"


def _resolve_node_type(node: dict[str, Any]) -> str:
    """从 React Flow 节点 JSON 解析 type（与 compiler.resolve_node_type 逻辑一致）。"""
    node_data = node.get("data") or {}
    if not isinstance(node_data, dict):
        node_data = {}
    node_type = node_data.get("type") or node.get("type") or node.get("node_type") or ""
    return str(node_type)


def iter_subflow_nodes(graph: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """返回 (node_id, node_data) 列表。"""
    items: list[tuple[str, dict[str, Any]]] = []
    for node in graph.get("nodes") or []:
        if _resolve_node_type(node) != CanvasNodeType.SUB_FLOW:
            continue
        node_id = str(node.get("id") or "")
        data = node.get("data") or {}
        if not isinstance(data, dict):
            data = {}
        items.append((node_id, data))
    return items


def _parse_sub_flow_id(node_data: dict[str, Any]) -> UUID:
    """解析并校验 SubFlow/LoopNode 的 sub_flow_id。"""
    raw = node_data.get("sub_flow_id")
    if not raw:
        raise BadRequestError("SubFlow 节点须配置 sub_flow_id")
    try:
        return UUID(str(raw))
    except ValueError as exc:
        raise BadRequestError("sub_flow_id 格式无效") from exc


async def resolve_subflow_graph(
    repo: FlowRepoLike,
    node_data: dict[str, Any],
    tenant_id: UUID,
) -> dict[str, Any]:
    """按 version_policy 加载子流程 graph_json。"""
    sub_flow_id = _parse_sub_flow_id(node_data)
    flow = await repo.get_by_id(sub_flow_id)
    if not flow or is_marked_deleted(flow) or flow.tenant_id != tenant_id:
        raise NotFoundError("子流程不存在")

    policy = str(node_data.get("version_policy") or VERSION_POLICY_PUBLISHED).strip().lower()
    if policy == VERSION_POLICY_PINNED:
        pinned = node_data.get("pinned_version")
        if pinned is None:
            raise BadRequestError("pinned 策略须配置 pinned_version")
        version = await repo.get_version(sub_flow_id, int(pinned))
        if not version:
            raise BadRequestError(f"子流程 pinned 版本 v{pinned} 不存在")
        return version.graph_json or {"nodes": [], "edges": []}

    if flow.status != FlowStatus.PUBLISHED:
        raise BadRequestError("子流程未发布")
    if flow.current_version <= 0:
        raise BadRequestError("子流程无可用版本")
    version = await repo.get_version(sub_flow_id, flow.current_version)
    if not version:
        raise BadRequestError("子流程无可用版本")
    return version.graph_json or {"nodes": [], "edges": []}


def _resolve_mapped_value(key: str, inputs: dict[str, Any], ctx: RunContext) -> Any:
    """input_mapping 源 key：优先当前 inputs，其次 parent ctx.inputs。"""
    if key in inputs and inputs[key] is not None:
        return inputs[key]
    if key in ctx.inputs and ctx.inputs[key] is not None:
        return ctx.inputs[key]
    return None


def build_child_context(
    parent_ctx: RunContext,
    inputs: dict[str, Any],
    node_data: dict[str, Any],
    *,
    parent_flow_id: str | None,
    parent_node_id: str,
    child_flow_id: str,
) -> RunContext:
    """构造子 run 上下文；input_mapping 写入 child inputs。"""
    child_inputs: dict[str, Any] = {}
    mapping = node_data.get("input_mapping") or {}
    if isinstance(mapping, dict):
        for target_key, source_key in mapping.items():
            if not isinstance(target_key, str) or not isinstance(source_key, str):
                continue
            if source_key.startswith("const:"):
                child_inputs[target_key] = source_key[6:]
                continue
            val = _resolve_mapped_value(source_key, inputs, parent_ctx)
            if val is not None:
                child_inputs[target_key] = val

    if not child_inputs:
        for key in ("query", "input"):
            if key in inputs and inputs[key] is not None:
                child_inputs.setdefault("query", inputs[key])
                break
        if not child_inputs and parent_ctx.inputs:
            child_inputs.update(dict(parent_ctx.inputs))

    kb_ids = list(parent_ctx.kb_ids)
    kb_override = node_data.get("kb_ids")
    if isinstance(kb_override, list) and kb_override:
        kb_ids = [str(x) for x in kb_override]

    return RunContext(
        tenant_id=parent_ctx.tenant_id,
        inputs=child_inputs,
        variables=dict(parent_ctx.variables),
        kb_ids=kb_ids,
        model_config_id=parent_ctx.model_config_id,
        system_prompt=parent_ctx.system_prompt,
        user_id=parent_ctx.user_id,
        permissions=parent_ctx.permissions,
        is_superuser=parent_ctx.is_superuser,
        agent_id=parent_ctx.agent_id,
        agent_config=dict(parent_ctx.agent_config),
        media=list(parent_ctx.media),
        generative_video_async=parent_ctx.generative_video_async,
        generative_image_async=parent_ctx.generative_image_async,
        current_flow_id=child_flow_id,
        parent_flow_id=parent_flow_id,
        parent_node_id=parent_node_id,
        subflow_depth=parent_ctx.subflow_depth + 1,
        run_subflow=parent_ctx.run_subflow,  # 传播子流程回调到子 context
        resolve_model=parent_ctx.resolve_model,  # 画布 LLM 模型解析回调透传到子流程
        usage_sink=parent_ctx.usage_sink,  # 画布 LLM 用量记录器透传到子流程
        kb_retrieval=parent_ctx.kb_retrieval,  # KB 检索绑定透传到子流程
        resolve_generative_image=parent_ctx.resolve_generative_image,  # 画布生图模型解析器透传到子流程
        resolve_generative_video=parent_ctx.resolve_generative_video,  # 画布生视频模型解析器透传到子流程
        submit_generative_image=parent_ctx.submit_generative_image,  # 生图异步提交回调透传到子流程
        submit_generative_video=parent_ctx.submit_generative_video,  # 生视频异步提交回调透传到子流程
        invoke_platform_tool=parent_ctx.invoke_platform_tool,  # 平台工具执行回调透传到子流程
        resolve_prompt_template=parent_ctx.resolve_prompt_template,  # prompt 模板解析回调透传到子流程
        load_scan_words=parent_ctx.load_scan_words,  # 敏感词表加载回调透传到子流程
        load_subflow_graph=parent_ctx.load_subflow_graph,  # 子流程图加载回调透传到子流程
        media_reader=parent_ctx.media_reader,  # 媒体读取器透传到子流程
        generate_image_sync=parent_ctx.generate_image_sync,  # 同步生图编排回调透传到子流程
        generate_video_sync=parent_ctx.generate_video_sync,  # 同步生视频编排回调透传到子流程
    )


def pick_subflow_output(result: Any, output_key: str | None) -> Any:
    """从子流程 run 结果中抽取 output_key 或默认 output 字段。"""
    if output_key:
        if isinstance(result, dict) and output_key in result:
            return result[output_key]
        return None
    if isinstance(result, dict) and "output" in result:
        return result["output"]
    return result


def summarize_child_steps(steps: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    """子 steps 摘要供主流程调试面板展示。"""
    summary: list[dict[str, Any]] = []
    for step in steps[:limit]:
        if not isinstance(step, dict):
            continue
        summary.append(
            {
                "node_id": step.get("node_id"),
                "node_type": step.get("node_type"),
                "output_preview": step.get("output_preview"),
            }
        )
    if len(steps) > limit:
        summary.append({"truncated": True, "total": len(steps)})
    return summary
