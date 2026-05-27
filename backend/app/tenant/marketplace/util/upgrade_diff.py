"""应用升级 diff：对比已安装资源与市场 manifest 目标值。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

_TEXT_LIMIT = 400


@dataclass
class UpgradeFieldChange:
    """单字段 before/after 对比。"""

    field: str
    label: str
    before: str | None
    after: str | None
    changed: bool


@dataclass
class UpgradeResourceDiff:
    """单个资源（KB/Flow/Agent）的字段变更集合。"""

    resource_type: str
    resource_id: UUID | None
    resource_name: str
    changes: list[UpgradeFieldChange] = field(default_factory=list)
    has_changes: bool = False


@dataclass
class UpgradePreviewData:
    """升级预览聚合结果（供 MarketplaceUpgradeMixin.preview_upgrade 序列化）。"""

    app_id: UUID
    app_name: str
    installed_version: str
    target_version: str
    can_upgrade: bool
    has_changes: bool
    message: str | None
    resources: list[UpgradeResourceDiff] = field(default_factory=list)


def _norm(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return str(value)


def _truncate(text: str | None) -> str | None:
    if text is None:
        return None
    if len(text) <= _TEXT_LIMIT:
        return text
    return text[: _TEXT_LIMIT - 1] + "…"


def _field(
    field_key: str,
    label: str,
    before: Any,
    after: Any,
) -> UpgradeFieldChange:
    """构造单字段 diff 项，长文本截断至 _TEXT_LIMIT。"""
    b = _norm(before)
    a = _norm(after)
    changed = b != a
    return UpgradeFieldChange(
        field=field_key,
        label=label,
        before=_truncate(b),
        after=_truncate(a),
        changed=changed,
    )


def _graph_counts(graph: dict | None) -> tuple[int, int]:
    if not graph or not isinstance(graph, dict):
        return 0, 0
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    return (
        len(nodes) if isinstance(nodes, list) else 0,
        len(edges) if isinstance(edges, list) else 0,
    )


def _graphs_equal(a: dict | None, b: dict | None) -> bool:
    try:
        return json.dumps(a or {}, sort_keys=True) == json.dumps(b or {}, sort_keys=True)
    except TypeError:
        return (a or {}) == (b or {})


def diff_knowledge_base(
    *,
    resource_id: UUID | None,
    current_name: str | None,
    current_description: str | None,
    target: dict,
) -> UpgradeResourceDiff:
    """对比知识库名称与描述。"""
    changes = [
        _field("name", "名称", current_name, target.get("name")),
        _field("description", "描述", current_description, target.get("description")),
    ]
    return UpgradeResourceDiff(
        resource_type="knowledge_base",
        resource_id=resource_id,
        resource_name=current_name or target.get("name") or "知识库",
        changes=changes,
        has_changes=any(c.changed for c in changes),
    )


def diff_flow(
    *,
    resource_id: UUID | None,
    current_name: str | None,
    current_description: str | None,
    current_graph: dict | None,
    target: dict,
) -> UpgradeResourceDiff:
    """对比流程元数据与 graph_json 结构（节点/边数）。"""
    target_graph = target.get("graph_json") if isinstance(target.get("graph_json"), dict) else None
    n_before, e_before = _graph_counts(current_graph)
    n_after, e_after = _graph_counts(target_graph)
    graph_changed = not _graphs_equal(current_graph, target_graph)
    changes = [
        _field("name", "名称", current_name, target.get("name")),
        _field("description", "描述", current_description, target.get("description")),
        _field("graph_nodes", "画布节点数", n_before, n_after),
        _field("graph_edges", "画布连线数", e_before, e_after),
        UpgradeFieldChange(
            field="graph_structure",
            label="画布结构",
            before="无变更" if not graph_changed else f"{n_before} 节点 / {e_before} 连线",
            after="无变更" if not graph_changed else f"{n_after} 节点 / {e_after} 连线",
            changed=graph_changed,
        ),
    ]
    return UpgradeResourceDiff(
        resource_type="flow",
        resource_id=resource_id,
        resource_name=current_name or target.get("name") or "流程",
        changes=changes,
        has_changes=any(c.changed for c in changes),
    )


def diff_agent(
    *,
    resource_id: UUID | None,
    current_name: str | None,
    current_description: str | None,
    current_system_prompt: str | None,
    target: dict,
) -> UpgradeResourceDiff:
    """对比智能体名称、描述与 system_prompt。"""
    changes = [
        _field("name", "名称", current_name, target.get("name")),
        _field("description", "描述", current_description, target.get("description")),
        _field("system_prompt", "系统提示词", current_system_prompt, target.get("system_prompt")),
    ]
    return UpgradeResourceDiff(
        resource_type="agent",
        resource_id=resource_id,
        resource_name=current_name or target.get("name") or "智能体",
        changes=changes,
        has_changes=any(c.changed for c in changes),
    )


def build_upgrade_preview(
    *,
    app_id: UUID,
    app_name: str,
    installed_version: str,
    target_version: str,
    resources: list[UpgradeResourceDiff],
) -> UpgradePreviewData:
    """汇总各资源 diff，判定 can_upgrade / has_changes 与用户提示文案。"""
    can_upgrade = installed_version != target_version
    has_changes = any(r.has_changes for r in resources)
    if not can_upgrade:
        message = "已是最新版本"
    elif not has_changes:
        message = "版本号有更新，但 manifest 字段与当前安装资源一致"
    else:
        message = None
    return UpgradePreviewData(
        app_id=app_id,
        app_name=app_name,
        installed_version=installed_version,
        target_version=target_version,
        can_upgrade=can_upgrade,
        has_changes=has_changes,
        message=message,
        resources=resources,
    )
