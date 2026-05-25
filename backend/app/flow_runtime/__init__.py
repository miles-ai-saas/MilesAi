"""流程节点与执行入口（画布由 LangGraph 编译运行）。

Agent.published_flow_id → get_flow_runtime().run(graph_json, ctx)。
"""

__all__ = ["get_flow_runtime", "RunContext", "RunResult", "FlowGraph"]


def __getattr__(name: str):
    """延迟导出，避免 import 环。"""
    if name == "get_flow_runtime":
        from app.flow_runtime.runtime_factory import get_flow_runtime

        return get_flow_runtime
    if name in ("RunContext", "RunResult", "FlowGraph"):
        from app.flow_runtime import types

        return getattr(types, name)
    raise AttributeError(name)
