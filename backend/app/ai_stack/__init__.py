"""LangChain / LangGraph / DeepAgents 集成（渐进落地）。"""

__all__ = [
    "ainvoke_chat",
    "embed_query_for_kb_sync",
    "embed_texts_for_kb_sync",
    "split_text",
    "rag_answer",
    "retrieve_hits",
    "run_rag_workflow",
    "should_use_langgraph_rag",
]


def __getattr__(name: str):
    if name in (
        "ainvoke_chat",
        "embed_query_for_kb_sync",
        "embed_texts_for_kb_sync",
        "split_text",
        "rag_answer",
        "retrieve_hits",
    ):
        from app.ai_stack import langchain as lc

        return getattr(lc, name)
    if name in ("run_rag_workflow", "should_use_langgraph_rag"):
        from app.ai_stack import langgraph as lg

        return getattr(lg, name)
    raise AttributeError(name)
