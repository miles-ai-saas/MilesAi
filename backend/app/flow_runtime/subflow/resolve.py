"""子流程 graph 解析与 RunContext 构造。"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError, NotFoundError
from app.core.soft_delete import is_marked_deleted
from app.flow_runtime.types import RunContext
from app.models.flow import Flow, FlowStatus
from app.tenant.flows.repositories.flow import FlowRepository

SUB_FLOW_NODE_TYPE = "SubFlow"
VERSION_POLICY_PUBLISHED = "published"
VERSION_POLICY_PINNED = "pinned"


def _resolve_node_type(node: dict[str, Any]) -> str:
    node_data = node.get("data") or {}
    if not isinstance(node_data, dict):
        node_data = {}
    node_type = node_data.get("type") or node.get("type") or node.get("node_type") or ""
    if node_type in ("genericNode", "customNode") and node_data.get("type"):
        node_type = node_data.get("type")
    return str(node_type)


def iter_subflow_nodes(graph: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """返回 (node_id, node_data) 列表。"""
    items: list[tuple[str, dict[str, Any]]] = []
    for node in graph.get("nodes") or []:
        if _resolve_node_type(node) != SUB_FLOW_NODE_TYPE:
            continue
        node_id = str(node.get("id") or "")
        data = node.get("data") or {}
        if not isinstance(data, dict):
            data = {}
        items.append((node_id, data))
    return items


def _parse_sub_flow_id(node_data: dict[str, Any]) -> UUID:
    raw = node_data.get("sub_flow_id")
    if not raw:
        raise BadRequestError("SubFlow 节点须配置 sub_flow_id")
    try:
        return UUID(str(raw))
    except ValueError as exc:
        raise BadRequestError("sub_flow_id 格式无效") from exc


async def resolve_subflow_graph(
    db: AsyncSession,
    node_data: dict[str, Any],
    tenant_id: UUID,
) -> dict[str, Any]:
    """按 version_policy 加载子流程 graph_json。"""
    sub_flow_id = _parse_sub_flow_id(node_data)
    repo = FlowRepository(db)
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
    )


def pick_subflow_output(result: Any, output_key: str | None) -> Any:
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
