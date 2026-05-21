"""可选：对接 PyPI 上的 langflow 包（未安装时使用 Builtin 运行时）。"""

from app.flow_runtime.builtin_runtime import BuiltinFlowRuntime
from app.flow_runtime.types import RunContext, RunResult


class OptionalLangflowAdapter:
    """若已安装第三方 langflow 包则启用；当前仍委托 Builtin 执行 graph_json。"""

    _builtin = BuiltinFlowRuntime()

    @classmethod
    def is_available(cls) -> bool:
        try:
            import langflow  # noqa: F401 — 第三方包名，非本仓库模块

            return True
        except ImportError:
            return False

    async def run(self, graph: dict, ctx: RunContext) -> RunResult:
        # 第三方 langflow API 随版本变化，统一经适配层扩展。
        # 后续可在此接入 langflow.load_flow_from_json + run。
        return await self._builtin.run(graph, ctx)
