"""SubFlow 编译期校验（published/pinned、环、深度）。

FlowService 保存/发布前调用；LoopNode 与 SubFlow 共用 sub_flow_id 校验逻辑。
仓储以 ``FlowRepoLike`` 契约注入（L1 ``FlowService`` 传 ``FlowRepository``）。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from miles_ai.flow_runtime.constants import MAX_SUBFLOW_DEPTH
from miles_ai.flow_runtime.subflow.contracts import FlowRepoLike
from miles_ai.flow_runtime.subflow.resolve import (
    VERSION_POLICY_PINNED,
    VERSION_POLICY_PUBLISHED,
    iter_subflow_nodes,
)
from miles_core.models.flow import Flow, FlowStatus
from miles_core.soft_delete import is_marked_deleted


def _compile_error(
    code: str,
    message: str,
    *,
    node_id: str | None = None,
) -> dict[str, Any]:
    """结构化校验错误（与 compiler._compile_error 字段一致）。"""
    return {"code": code, "message": message, "node_id": node_id}


def _sub_flow_id_from_data(node_data: dict[str, Any]) -> str | None:
    raw = node_data.get("sub_flow_id")
    if not raw:
        return None
    return str(raw)


async def _load_flow_graph_for_analysis(
    repo: FlowRepoLike,
    flow: Flow,
    *,
    pinned_version: int | None = None,
) -> dict[str, Any]:
    if pinned_version is not None:
        version = await repo.get_version(flow.id, pinned_version)
        return (version.graph_json if version else None) or {"nodes": [], "edges": []}
    if flow.current_version <= 0:
        return {"nodes": [], "edges": []}
    version = await repo.get_version(flow.id, flow.current_version)
    return (version.graph_json if version else None) or {"nodes": [], "edges": []}


async def _direct_subflow_ids(
    repo: FlowRepoLike,
    flow: Flow,
    graph: dict[str, Any],
) -> set[str]:
    ids: set[str] = set()
    for _nid, data in iter_subflow_nodes(graph):
        sub_id = _sub_flow_id_from_data(data)
        if sub_id:
            ids.add(sub_id)
    return ids


async def _max_chain_depth(
    repo: FlowRepoLike,
    tenant_id: UUID,
    start_flow_id: UUID,
    start_graph: dict[str, Any],
    *,
    cache: dict[str, set[str]],
    visiting: set[str],
    current_depth: int,
) -> int:
    """DFS 计算子流程引用链最大深度，检测间接环。"""
    key = str(start_flow_id)
    if key in visiting:
        return current_depth
    visiting.add(key)
    try:
        if key not in cache:
            flow = await repo.get_by_id(start_flow_id)
            if not flow or is_marked_deleted(flow) or flow.tenant_id != tenant_id:
                cache[key] = set()
            else:
                graph = await _load_flow_graph_for_analysis(repo, flow)
                cache[key] = await _direct_subflow_ids(repo, flow, graph)
        child_ids = cache[key]
        if not child_ids:
            return current_depth
        max_child = current_depth
        for cid in child_ids:
            try:
                child_uuid = UUID(cid)
            except ValueError:
                continue
            depth = await _max_chain_depth(
                repo,
                tenant_id,
                child_uuid,
                {},
                cache=cache,
                visiting=visiting,
                current_depth=current_depth + 1,
            )
            max_child = max(max_child, depth)
        return max_child
    finally:
        visiting.discard(key)


async def validate_subflow_references(
    repo: FlowRepoLike,
    graph: dict[str, Any],
    *,
    tenant_id: UUID,
    current_flow_id: UUID | None,
) -> list[dict[str, Any]]:
    """校验画布中所有 SubFlow 引用；返回结构化错误列表（空表示通过）。"""
    errors: list[dict[str, Any]] = []

    for node_id, data in iter_subflow_nodes(graph):
        sub_raw = _sub_flow_id_from_data(data)
        if not sub_raw:
            errors.append(
                _compile_error(
                    "missing_sub_flow_id",
                    "SubFlow 节点须配置 sub_flow_id",
                    node_id=node_id,
                )
            )
            continue
        if current_flow_id and sub_raw == str(current_flow_id):
            errors.append(
                _compile_error(
                    "subflow_self",
                    "SubFlow 不可调用自身流程",
                    node_id=node_id,
                )
            )
            continue
        try:
            sub_flow_id = UUID(sub_raw)
        except ValueError:
            errors.append(
                _compile_error(
                    "missing_sub_flow_id",
                    "sub_flow_id 格式无效",
                    node_id=node_id,
                )
            )
            continue

        flow = await repo.get_by_id(sub_flow_id)
        if not flow or is_marked_deleted(flow) or flow.tenant_id != tenant_id:
            errors.append(
                _compile_error(
                    "subflow_not_found",
                    "子流程不存在或无权访问",
                    node_id=node_id,
                )
            )
            continue

        policy = str(data.get("version_policy") or VERSION_POLICY_PUBLISHED).strip().lower()
        if policy == VERSION_POLICY_PINNED:
            pinned = data.get("pinned_version")
            if pinned is None:
                errors.append(
                    _compile_error(
                        "subflow_pinned_missing",
                        "pinned 策略须配置 pinned_version",
                        node_id=node_id,
                    )
                )
            else:
                version = await repo.get_version(sub_flow_id, int(pinned))
                if not version:
                    errors.append(
                        _compile_error(
                            "subflow_pinned_missing",
                            f"子流程 pinned 版本 v{pinned} 不存在",
                            node_id=node_id,
                        )
                    )
        elif flow.status != FlowStatus.PUBLISHED:
            errors.append(
                _compile_error(
                    "subflow_not_published",
                    "子流程未发布，无法引用",
                    node_id=node_id,
                )
            )
        elif flow.current_version <= 0:
            errors.append(
                _compile_error(
                    "subflow_not_published",
                    "子流程无可用版本",
                    node_id=node_id,
                )
            )

    if current_flow_id:
        for node_id, data in iter_subflow_nodes(graph):
            sub_raw = _sub_flow_id_from_data(data)
            if not sub_raw or sub_raw == str(current_flow_id):
                continue
            reverse_flow = await repo.get_by_id(UUID(sub_raw))
            if not reverse_flow or is_marked_deleted(reverse_flow):
                continue
            child_graph = await _load_flow_graph_for_analysis(repo, reverse_flow)
            for _cid, cdata in iter_subflow_nodes(child_graph):
                back = _sub_flow_id_from_data(cdata)
                if back == str(current_flow_id):
                    errors.append(
                        _compile_error(
                            "subflow_cycle",
                            f"子流程依赖存在环：{sub_raw} → {current_flow_id}",
                            node_id=node_id,
                        )
                    )

        cache: dict[str, set[str]] = {}
        max_depth = await _max_chain_depth(
            repo,
            tenant_id,
            current_flow_id,
            graph,
            cache=cache,
            visiting=set(),
            current_depth=0,
        )
        if max_depth > MAX_SUBFLOW_DEPTH:
            errors.append(
                _compile_error(
                    "subflow_max_depth",
                    f"子流程嵌套深度超过 {MAX_SUBFLOW_DEPTH} 层",
                )
            )

    return errors
