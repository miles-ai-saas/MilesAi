"""
React Flow ``graph_json`` → LangGraph ``StateGraph`` 编译器（画布流程 L3）。

目录职责
--------
- ``report.py``：``FlowCompileReport``、节点类型解析、结构化错误。
- ``validate.py``：``validate_graph_for_compile`` / ``can_compile_flow_graph``。
- ``state.py``：入边聚合、条件路由、最终输出解析。
- ``build.py``：``build_canvas_graph``。
- ``run.py``：``run_compiled_canvas``。

与 Agent RAG 图的区别见各子模块注释；``SUPPORTED_CANVAS_NODE_TYPES`` 与
``flow_runtime.nodes.registry`` 键名必须一致。

对外::

    from miles_ai.integrations.langgraph.compiler import build_canvas_graph, validate_graph_for_compile
"""

from miles_ai.integrations.langgraph.compiler.build import build_canvas_graph
from miles_ai.integrations.langgraph.compiler.report import (
    FlowCompileReport,
    SUPPORTED_CANVAS_NODE_TYPES,
    _error_to_str,
    resolve_node_type,
)
from miles_ai.integrations.langgraph.compiler.run import run_compiled_canvas
from miles_ai.integrations.langgraph.compiler.validate import can_compile_flow_graph, validate_graph_for_compile

__all__ = [
    "FlowCompileReport",
    "SUPPORTED_CANVAS_NODE_TYPES",
    "_error_to_str",
    "build_canvas_graph",
    "can_compile_flow_graph",
    "resolve_node_type",
    "run_compiled_canvas",
    "validate_graph_for_compile",
]
