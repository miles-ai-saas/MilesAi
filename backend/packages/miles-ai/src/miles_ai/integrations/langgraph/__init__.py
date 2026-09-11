"""
LangGraph 集成包。

子模块
------
- ``runner``：Agent RAG 图执行（``run_rag_workflow``）
- ``compiler`` / ``flow_runner``：画布 ``graph_json`` 编译与运行
- ``graphs.rag_qa``：检索→评分→生成/重试/兜底
- ``checkpointer``：Redis/内存多轮状态

对外惰性导出见 ``__all__``；画布与 RAG 图为两套独立编译产物。
"""

__all__ = ["run_rag_workflow", "should_use_langgraph_rag"]


def __getattr__(name: str):
    """延迟导出 runner，避免 import 环。"""
    if name in __all__:
        from miles_ai.integrations.langgraph.runner import run_rag_workflow, should_use_langgraph_rag

        return {"run_rag_workflow": run_rag_workflow, "should_use_langgraph_rag": should_use_langgraph_rag}[name]
    raise AttributeError(name)
