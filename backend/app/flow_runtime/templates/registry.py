"""
内置流程画布模板注册表与加载。

模板 JSON 存放于同目录；``list_flow_templates`` 供 ``GET /flows/templates``，
``load_flow_template_graph`` 供市场种子与 API 加载画布 JSON。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_TEMPLATES_DIR = Path(__file__).resolve().parent

_EMPTY_GRAPH: dict[str, Any] = {"nodes": [], "edges": []}


@dataclass(frozen=True, slots=True)
class FlowTemplateSpec:
    """内置画布模板注册项。"""

    id: str  # 模板标识（如 rag、blank）
    label: str  # 展示名称
    hint: str  # 简短说明
    default_name: str  # 建议的流程名称
    graph_file: str | None  # 同目录 JSON 文件名；blank 为 None
    insertable: bool = True  # 编辑页是否出现在「插入模板」


FLOW_TEMPLATE_REGISTRY: tuple[FlowTemplateSpec, ...] = (
    FlowTemplateSpec(
        id="blank",
        label="空白画布",
        hint="从零拖拽节点",
        default_name="新流程",
        graph_file=None,
        insertable=False,
    ),
    FlowTemplateSpec(
        id="rag",
        label="RAG 问答",
        hint="检索 → 提示词 → LLM → 输出",
        default_name="RAG 问答流程",
        graph_file="rag_flow.json",
    ),
    FlowTemplateSpec(
        id="simple_llm",
        label="简单对话",
        hint="用户输入 → 大模型 → 输出",
        default_name="对话流程",
        graph_file="simple_llm.json",
    ),
    FlowTemplateSpec(
        id="rag_with_grade",
        label="RAG 问答（评分分支）",
        hint="检索 → 相关性评分 → 条件分支",
        default_name="RAG 评分流程",
        graph_file="rag_flow_with_grade.json",
        insertable=False,
    ),
)

_REGISTRY_BY_ID = {spec.id: spec for spec in FLOW_TEMPLATE_REGISTRY}


def _read_graph_file(name: str) -> dict[str, Any]:
    """读取 templates 目录下 JSON 画布文件。"""
    path = _TEMPLATES_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))


def load_flow_template_graph(template_id: str) -> dict[str, Any]:
    """按模板 id 加载 graph_json；未知 id 抛出 KeyError。"""
    spec = _REGISTRY_BY_ID[template_id]
    if spec.graph_file is None:
        return dict(_EMPTY_GRAPH)
    return _read_graph_file(spec.graph_file)


def list_flow_templates(*, insertable_only: bool = False) -> list[dict[str, Any]]:
    """
    返回模板列表（含完整 graph_json），供 API 与调试使用。

    ``insertable_only``: 仅含可在编辑页「插入模板」的项（排除 blank）。
    """
    items: list[dict[str, Any]] = []
    for spec in FLOW_TEMPLATE_REGISTRY:
        if insertable_only and not spec.insertable:
            continue
        items.append(
            {
                "id": spec.id,
                "label": spec.label,
                "hint": spec.hint,
                "default_name": spec.default_name,
                "insertable": spec.insertable,
                "graph_json": load_flow_template_graph(spec.id),
            }
        )
    return items
