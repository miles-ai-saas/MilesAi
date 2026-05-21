"""流程节点与执行入口（画布由 LangGraph 编译运行）。"""

__all__ = ["get_flow_runtime", "RunContext", "RunResult", "FlowGraph"]


def __getattr__(name: str):
    if name == "get_flow_runtime":
        from app.flow_runtime.runtime_factory import get_flow_runtime

        return get_flow_runtime
    if name in ("RunContext", "RunResult", "FlowGraph"):
        from app.flow_runtime import types

        return getattr(types, name)
    raise AttributeError(name)
