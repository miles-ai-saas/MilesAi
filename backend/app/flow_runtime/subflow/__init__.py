"""子流程解析与编译期校验。"""

from app.flow_runtime.constants import MAX_SUBFLOW_DEPTH
from app.flow_runtime.subflow.resolve import build_child_context, resolve_subflow_graph

__all__ = [
    "MAX_SUBFLOW_DEPTH",
    "build_child_context",
    "resolve_subflow_graph",
    "validate_subflow_references",
]


def __getattr__(name: str):
    if name == "validate_subflow_references":
        from app.flow_runtime.subflow.validate import validate_subflow_references

        return validate_subflow_references
    raise AttributeError(name)
