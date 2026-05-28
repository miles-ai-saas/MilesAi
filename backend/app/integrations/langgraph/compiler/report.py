"""编译诊断结构与节点类型解析。"""

from typing import Any

from app.flow_runtime.nodes.registry import NODE_REGISTRY

SUPPORTED_CANVAS_NODE_TYPES = frozenset(NODE_REGISTRY.keys())


def resolve_node_type(node: dict[str, Any]) -> str:
    """从 React Flow 节点 JSON 解析 registry 键名。"""
    node_data = node.get("data") or {}
    if not isinstance(node_data, dict):
        node_data = {}
    node_type = node_data.get("type") or node.get("type") or node.get("node_type") or ""
    return str(node_type)


def _compile_error(
    code: str,
    message: str,
    *,
    node_id: str | None = None,
) -> dict[str, Any]:
    """结构化编译错误；``errors`` 字符串列表与之同步生成。"""
    return {"code": code, "message": message, "node_id": node_id}


def _error_to_str(err: dict[str, Any]) -> str:
    """将结构化编译错误格式化为 ``[node_id] message`` 便于展示。"""
    nid = err.get("node_id")
    msg = str(err.get("message") or "")
    if nid:
        return f"[{nid}] {msg}"
    return msg


class FlowCompileReport:
    """画布编译诊断结果（工作台「编译预览」/ ``FlowService`` 校验用）。"""

    __slots__ = (
        "compilable",
        "engine",
        "node_order",
        "node_types",
        "execution_layers",
        "parallel_groups",
        "conditional_nodes",
        "errors",
        "error_details",
    )

    def __init__(
        self,
        *,
        compilable: bool,
        engine: str,
        node_order: list[str],
        node_types: list[str],
        execution_layers: list[list[str]],
        parallel_groups: list[list[str]],
        conditional_nodes: list[str],
        errors: list[str],
        error_details: list[dict[str, Any]] | None = None,
    ):
        """compilable=False 时 engine 为 ``builtin``，仅用于诊断不可执行。"""
        self.compilable = compilable
        self.engine = engine
        self.node_order = node_order
        self.node_types = node_types
        self.execution_layers = execution_layers
        self.parallel_groups = parallel_groups
        self.conditional_nodes = conditional_nodes
        self.errors = errors
        self.error_details = error_details or []

    def to_dict(self) -> dict[str, Any]:
        """序列化为 API / 编译预览 JSON。"""
        return {
            "compilable": self.compilable,
            "engine": self.engine,
            "node_order": self.node_order,
            "node_types": self.node_types,
            "execution_layers": self.execution_layers,
            "parallel_groups": self.parallel_groups,
            "conditional_nodes": self.conditional_nodes,
            "errors": self.errors,
            "error_details": self.error_details,
        }
