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


async def _direct_subflow_ids(graph: dict[str, Any]) -> set[str]:
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
                cache[key] = await _direct_subflow_ids(graph)
        child_ids = cache[key]
        if not child_ids:
            return current_depth
        max_child = current_depth
        for cid in child_ids:
            try:
                child_uuid = UUID(cid)
            except ValueError:
                # 静默可接受：子流程 ID 非 UUID 即跳过该分支；节点级校验已另行登记该错误。
                continue
            depth = await _max_chain_depth(
                repo,
                tenant_id,
                child_uuid,
                cache=cache,
                visiting=visiting,
                current_depth=current_depth + 1,
            )
            max_child = max(max_child, depth)
        return max_child
    finally:
        visiting.discard(key)


async def _pinned_version_errors(
    repo: FlowRepoLike,
    sub_flow_id: UUID,
    node_id: str,
    data: dict[str, Any],
) -> list[dict[str, Any]]:
    """``pinned`` 策略：须给出 ``pinned_version`` 且该版本确实存在。"""
    pinned = data.get("pinned_version")
    if pinned is None:
        return [
            _compile_error(
                "subflow_pinned_missing",
                "pinned 策略须配置 pinned_version",
                node_id=node_id,
            )
        ]
    version = await repo.get_version(sub_flow_id, int(pinned))
    if not version:
        return [
            _compile_error(
                "subflow_pinned_missing",
                f"子流程 pinned 版本 v{pinned} 不存在",
                node_id=node_id,
            )
        ]
    return []


async def _validate_subflow_node(
    repo: FlowRepoLike,
    node_id: str,
    data: dict[str, Any],
    *,
    tenant_id: UUID,
    current_flow_id: UUID | None,
) -> list[dict[str, Any]]:
    """单个 SubFlow 节点的引用校验：self / 格式 / 存在性 / 版本策略。"""
    sub_raw = _sub_flow_id_from_data(data)
    if not sub_raw:
        return [
            _compile_error(
                "missing_sub_flow_id",
                "SubFlow 节点须配置 sub_flow_id",
                node_id=node_id,
            )
        ]
    if current_flow_id and sub_raw == str(current_flow_id):
        return [
            _compile_error(
                "subflow_self",
                "SubFlow 不可调用自身流程",
                node_id=node_id,
            )
        ]
    try:
        sub_flow_id = UUID(sub_raw)
    except ValueError:
        return [
            _compile_error(
                "missing_sub_flow_id",
                "sub_flow_id 格式无效",
                node_id=node_id,
            )
        ]

    flow = await repo.get_by_id(sub_flow_id)
    if not flow or is_marked_deleted(flow) or flow.tenant_id != tenant_id:
        return [
            _compile_error(
                "subflow_not_found",
                "子流程不存在或无权访问",
                node_id=node_id,
            )
        ]

    policy = str(data.get("version_policy") or VERSION_POLICY_PUBLISHED).strip().lower()
    if policy == VERSION_POLICY_PINNED:
        return await _pinned_version_errors(repo, sub_flow_id, node_id, data)
    if flow.status != FlowStatus.PUBLISHED:
        return [
            _compile_error(
                "subflow_not_published",
                "子流程未发布，无法引用",
                node_id=node_id,
            )
        ]
    if flow.current_version <= 0:
        return [
            _compile_error(
                "subflow_not_published",
                "子流程无可用版本",
                node_id=node_id,
            )
        ]
    return []


async def _cycle_errors(
    repo: FlowRepoLike,
    graph: dict[str, Any],
    current_flow_id: UUID,
) -> list[dict[str, Any]]:
    """反向引用检查：子流程的图里若回指本流程即构成环。

    只看一层，间接环由 ``_max_chain_depth`` 兜住。``sub_flow_id`` 不可解析的节点
    已在节点级校验记为错误，此处跳过（不能再调 ``UUID()`` 抛错）。
    """
    errors: list[dict[str, Any]] = []
    for node_id, data in iter_subflow_nodes(graph):
        sub_raw = _sub_flow_id_from_data(data)
        if not sub_raw or sub_raw == str(current_flow_id):
            continue
        try:
            child_id = UUID(sub_raw)
        except ValueError:
            # 静默可接受：sub_flow_id 不可解析的节点已在节点级校验记为错误，此处跳过即可（见本函数 docstring）。
            continue
        child = await repo.get_by_id(child_id)
        if not child or is_marked_deleted(child):
            continue
        child_graph = await _load_flow_graph_for_analysis(repo, child)
        for _cid, cdata in iter_subflow_nodes(child_graph):
            if _sub_flow_id_from_data(cdata) == str(current_flow_id):
                errors.append(
                    _compile_error(
                        "subflow_cycle",
                        f"子流程依赖存在环：{sub_raw} → {current_flow_id}",
                        node_id=node_id,
                    )
                )
    return errors


async def _max_depth_errors(
    repo: FlowRepoLike,
    tenant_id: UUID,
    current_flow_id: UUID,
) -> list[dict[str, Any]]:
    """子流程引用链超过 ``MAX_SUBFLOW_DEPTH`` 层时给出错误。"""
    max_depth = await _max_chain_depth(
        repo,
        tenant_id,
        current_flow_id,
        cache={},
        visiting=set(),
        current_depth=0,
    )
    if max_depth <= MAX_SUBFLOW_DEPTH:
        return []
    return [
        _compile_error(
            "subflow_max_depth",
            f"子流程嵌套深度超过 {MAX_SUBFLOW_DEPTH} 层",
        )
    ]


async def validate_subflow_references(
    repo: FlowRepoLike,
    graph: dict[str, Any],
    *,
    tenant_id: UUID,
    current_flow_id: UUID | None,
) -> list[dict[str, Any]]:
    """校验画布中所有 SubFlow 引用；返回结构化错误列表（空表示通过）。

    三类校验依次累积：逐节点引用校验 → 反向引用环 → 引用链深度上限。
    后两项需要知道「本流程是谁」才能判环，故仅在 ``current_flow_id`` 存在时执行。
    """
    errors: list[dict[str, Any]] = []
    for node_id, data in iter_subflow_nodes(graph):
        errors.extend(
            await _validate_subflow_node(
                repo,
                node_id,
                data,
                tenant_id=tenant_id,
                current_flow_id=current_flow_id,
            )
        )

    if not current_flow_id:
        return errors
    errors.extend(await _cycle_errors(repo, graph, current_flow_id))
    errors.extend(await _max_depth_errors(repo, tenant_id, current_flow_id))
    return errors
