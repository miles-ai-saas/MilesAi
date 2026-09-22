"""LangChain / LangGraph / LiteLLM / DeepAgents 集成（L3）。

包根仅惰性转发仍留在本包的公开符号；RAG / 画布编排见 ``miles_ai.rag`` /
``miles_ai.flow_runtime``。
"""

__all__ = [
    "ainvoke_chat",
    "get_chat_model",
    "checkpoint_backend",
    "get_checkpointer",
    "init_langgraph_checkpointer",
    "shutdown_langgraph_checkpointer",
]


def __getattr__(name: str):
    if name in ("ainvoke_chat", "get_chat_model"):
        from miles_integrations import langchain as lc

        return getattr(lc, name)
    if name in (
        "checkpoint_backend",
        "get_checkpointer",
        "init_langgraph_checkpointer",
        "shutdown_langgraph_checkpointer",
    ):
        from miles_integrations import langgraph as lg

        return getattr(lg, name)
    raise AttributeError(name)
