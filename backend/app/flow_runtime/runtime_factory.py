"""流程执行入口：React Flow graph_json → integrations.langgraph.flow_runner。

RAG 节点（KnowledgeSearch）内部调用 app.rag.generate.retrieve_hits。
"""

from functools import lru_cache

from app.integrations.langgraph.flow_runner import run_flow_graph
from app.flow_runtime.types import RunContext, RunResult


class LangGraphFlowRuntime:
    """流程运行时门面，委托 integrations.langgraph.flow_runner。"""

    async def run(self, graph: dict, ctx: RunContext) -> RunResult:
        """执行 React Flow 导出的 graph_json。"""
        return await run_flow_graph(graph, ctx)


@lru_cache
def get_flow_runtime() -> LangGraphFlowRuntime:
    """进程内单例 FlowRuntime（Agent 发布流程对话用）。"""
    return LangGraphFlowRuntime()
