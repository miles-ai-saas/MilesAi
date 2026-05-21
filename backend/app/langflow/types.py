from dataclasses import dataclass, field
from typing import Any


@dataclass
class FlowGraph:
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
