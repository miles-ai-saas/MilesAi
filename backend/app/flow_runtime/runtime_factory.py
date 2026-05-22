"""流程执行入口：graph_json 统一由 LangGraph 编译运行。"""

from functools import lru_cache

from app.integrations.langgraph.flow_runner import run_flow_graph
from app.flow_runtime.types import RunContext, RunResult


class LangGraphFlowRuntime:
    async def run(self, graph: dict, ctx: RunContext) -> RunResult:
        return await run_flow_graph(graph, ctx)


@lru_cache
def get_flow_runtime() -> LangGraphFlowRuntime:
    return LangGraphFlowRuntime()
