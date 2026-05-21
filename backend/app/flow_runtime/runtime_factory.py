from functools import lru_cache

from app.flow_runtime.builtin_runtime import BuiltinFlowRuntime
from app.flow_runtime.optional_langflow_adapter import OptionalLangflowAdapter


@lru_cache
def get_flow_runtime():
    if OptionalLangflowAdapter.is_available():
        return OptionalLangflowAdapter()
    return BuiltinFlowRuntime()
