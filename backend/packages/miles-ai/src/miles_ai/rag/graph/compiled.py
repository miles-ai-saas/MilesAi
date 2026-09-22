"""
带 checkpointer 的 RAG QA 编译图单例（L2）。

由 ``miles_server`` 的 lifespan 在 ``init_langgraph_checkpointer()`` 之后调用
``bind_rag_graph()`` 绑定；未绑定时 ``get_compiled_rag_graph()`` 回退
``build_rag_qa_graph().compile(MemorySaver())``（**不缓存**回退实例，与拆分前一致）。

多轮状态后端的选择与释放见 ``miles_integrations.langgraph.checkpointer``。
"""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from miles_ai.rag.graph.rag_qa import build_rag_qa_graph

_compiled_rag_graph: Any = None


def get_compiled_rag_graph() -> Any:
    """返回已绑定的 RAG 编译图；未绑定时回退内存 checkpointer 的一次性编译实例。"""
    if _compiled_rag_graph is None:
        return build_rag_qa_graph().compile(checkpointer=MemorySaver())
    return _compiled_rag_graph


def bind_rag_graph() -> None:
    """用当前 checkpointer 编译并缓存 RAG 图；由应用 lifespan 在 checkpointer 初始化后调用。"""
    global _compiled_rag_graph

    from miles_integrations.langgraph.checkpointer import get_checkpointer

    _compiled_rag_graph = build_rag_qa_graph().compile(checkpointer=get_checkpointer())


def unbind_rag_graph() -> None:
    """清除进程内缓存的编译图；由应用关闭时调用。"""
    global _compiled_rag_graph
    _compiled_rag_graph = None
