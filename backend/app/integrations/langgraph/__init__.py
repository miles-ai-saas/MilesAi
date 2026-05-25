"""LangGraph 流程编排（RAG 工作流、画布编译、checkpointer）。"""

__all__ = ["run_rag_workflow", "should_use_langgraph_rag"]


def __getattr__(name: str):
    """延迟导出 runner，避免 import 环。"""
    if name in __all__:
        from app.integrations.langgraph.runner import run_rag_workflow, should_use_langgraph_rag

        return {"run_rag_workflow": run_rag_workflow, "should_use_langgraph_rag": should_use_langgraph_rag}[
            name
        ]
    raise AttributeError(name)
