"""Langflow 内嵌适配器（可选依赖，安装 langflow 后自动启用）。"""

from app.langflow.builtin_runtime import BuiltinFlowRuntime
from app.langflow.types import RunContext, RunResult


class LangflowAdapter:
    """包装 Langflow 运行时；不可用时回退 Builtin。"""

    _builtin = BuiltinFlowRuntime()

    @classmethod
    def is_available(cls) -> bool:
        try:
            import langflow  # noqa: F401

            return True
        except ImportError:
            return False

    async def run(self, graph: dict, ctx: RunContext) -> RunResult:
        # Langflow 完整内嵌 API 随版本变化，统一经适配层扩展。
        # 当前版本：若已安装 langflow 仍用 Builtin 执行 graph_json，保证行为一致。
        # 后续可在此接入 langflow.load_flow_from_json + run。
        return await self._builtin.run(graph, ctx)
