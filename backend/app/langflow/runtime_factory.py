from functools import lru_cache

from app.langflow.builtin_runtime import BuiltinFlowRuntime
from app.langflow.langflow_adapter import LangflowAdapter


@lru_cache
def get_flow_runtime():
    if LangflowAdapter.is_available():
        return LangflowAdapter()
    return BuiltinFlowRuntime()
