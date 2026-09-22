"""
流程执行门面（L2）。

``LangGraphFlowRuntime.run`` 委托 ``flow_runtime.graph_runner.run_flow_graph``，
编译与节点分发见 ``flow_runtime.compiler`` + ``flow_runtime.nodes.registry``。

典型调用方：智能体 ``published_flow_id`` 对话、流程调试 API。
"""

from functools import lru_cache

from miles_ai.flow_runtime.graph_runner import run_flow_graph
from miles_ai.flow_runtime.types import RunContext, RunResult


class LangGraphFlowRuntime:
    """流程运行时门面，委托 flow_runtime.graph_runner。"""

    async def run(self, graph: dict, ctx: RunContext) -> RunResult:
        """执行 React Flow 导出的 graph_json。"""
        return await run_flow_graph(graph, ctx)


@lru_cache
def get_flow_runtime() -> LangGraphFlowRuntime:
    """进程内单例 FlowRuntime（Agent 发布流程对话用）。"""
    return LangGraphFlowRuntime()
