"""
Agent RAG 的 LangGraph 引擎（L2）。

组成
----
- ``rag_qa``：``build_rag_qa_graph`` —— retrieve → grade → generate | retry | fallback
- ``runner``：``run_rag_workflow`` / ``should_use_langgraph_rag`` / ``build_rag_thread_id``
- ``grading``：``evaluate_relevance`` 等评分逻辑（画布 RelevanceGrade 节点亦复用）
- ``constants``：``RELEVANCE_*`` 三态与 ``GRADE_BRANCH_HANDLES``
- ``state``：``RAGGraphState``

画布 ``graph_json`` 的编译与运行见 ``miles_ai.flow_runtime``，与本子包为两套独立编译产物；
多轮状态持久化后端见 ``miles_integrations.langgraph.checkpointer``。
"""

__all__ = [
    "GRADE_BRANCH_HANDLES",
    "RELEVANCE_GOOD",
    "RELEVANCE_NONE",
    "RELEVANCE_POOR",
    "RAGGraphState",
    "build_rag_qa_graph",
    "build_rag_thread_id",
    "evaluate_relevance",
    "llm_grade_relevance",
    "parse_llm_grade_response",
    "run_rag_workflow",
    "should_use_langgraph_rag",
]


def __getattr__(name: str):
    """延迟导出，避免包导入期拉起 ``runner`` / ``rag_qa``（及其对 checkpointer 的依赖）。"""
    if name in ("RELEVANCE_GOOD", "RELEVANCE_NONE", "RELEVANCE_POOR", "GRADE_BRANCH_HANDLES"):
        from miles_ai.rag.graph import constants

        return getattr(constants, name)
    if name == "RAGGraphState":
        from miles_ai.rag.graph import state

        return state.RAGGraphState
    if name in ("evaluate_relevance", "llm_grade_relevance", "parse_llm_grade_response", "_score_grade"):
        from miles_ai.rag.graph import grading

        return getattr(grading, name)
    if name == "build_rag_qa_graph":
        from miles_ai.rag.graph.rag_qa import build_rag_qa_graph

        return build_rag_qa_graph
    if name in ("run_rag_workflow", "should_use_langgraph_rag", "build_rag_thread_id"):
        from miles_ai.rag.graph import runner

        return getattr(runner, name)
    raise AttributeError(name)
