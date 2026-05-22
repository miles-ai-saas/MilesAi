"""LangGraph 流程编排。"""

__all__ = ["run_rag_workflow", "should_use_langgraph_rag"]


def __getattr__(name: str):
    if name in __all__:
        from app.integrations.langgraph.runner import run_rag_workflow, should_use_langgraph_rag

        return {"run_rag_workflow": run_rag_workflow, "should_use_langgraph_rag": should_use_langgraph_rag}[
            name
        ]
    raise AttributeError(name)
