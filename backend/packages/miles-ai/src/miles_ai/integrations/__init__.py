"""LangChain / LangGraph / DeepAgents 集成（渐进落地）。"""

__all__ = [
    "ainvoke_chat",
    "rag_answer",
    "retrieve_hits",
    "run_rag_workflow",
    "should_use_langgraph_rag",
    "split_text",
]


def __getattr__(name: str):
    if name in (
        "ainvoke_chat",
        "split_text",
        "rag_answer",
        "retrieve_hits",
    ):
        from miles_ai.integrations import langchain as lc

        return getattr(lc, name)
    if name in ("run_rag_workflow", "should_use_langgraph_rag"):
        from miles_ai.integrations import langgraph as lg

        return getattr(lg, name)
    raise AttributeError(name)
