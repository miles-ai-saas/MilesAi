"""流程运行时 DTO：React Flow graph_json 与单次 run 的上下文/结果。"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FlowGraph:
    """nodes + edges，与前端画布导出结构一致。"""
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]

    @classmethod
    def from_dict(cls, data: dict) -> "FlowGraph":
        return cls(
            nodes=data.get("nodes") or [],
            edges=data.get("edges") or [],
        )


@dataclass
class RunContext:
    """单次执行注入：inputs 为入口变量，kb_ids/model 供 RAG/LLM 节点读取。"""

    tenant_id: str
    inputs: dict[str, Any] = field(default_factory=dict)
    variables: dict[str, Any] = field(default_factory=dict)
    kb_ids: list[str] = field(default_factory=list)
    model_config_id: str | None = None
    system_prompt: str | None = None


@dataclass
class RunResult:
    output: Any
    steps: list[dict[str, Any]] = field(default_factory=list)
