"""
流程运行时对外门面（惰性 ``__getattr__``）。

典型调用
--------
- 智能体：``Agent.published_flow_id`` → ``get_flow_runtime().run(graph_json, RunContext)``
- 工作台调试：``FlowService.run``（可传入 ``kb_ids`` 供 KnowledgeSearch）

与 RAG 关系：画布内检索走 ``nodes.rag_nodes``，不经过 Agent ``rag_qa`` LangGraph。
"""

__all__ = ["FlowGraph", "RunContext", "RunResult", "get_flow_runtime"]


def __getattr__(name: str):
    """延迟导出，避免 import 环。"""
    if name == "get_flow_runtime":
        from miles_ai.flow_runtime.runtime_factory import get_flow_runtime

        return get_flow_runtime
    if name in ("RunContext", "RunResult", "FlowGraph"):
        from miles_ai.flow_runtime import types

        return getattr(types, name)
    raise AttributeError(name)
