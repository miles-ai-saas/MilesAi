"""Rerank invoke_mode 与 ModelConfig.extra 键名。

request_format：flat（qwen3-rerank）或 nested（经典 DashScope input/parameters）。
"""

INVOKE_MODE_DASHSCOPE = "dashscope"
INVOKE_MODE_OPENAI_COMPATIBLE = "openai_compatible"

EXTRA_INVOKE_MODE = "invoke_mode"
EXTRA_RERANK_INSTRUCT = "rerank_instruct"
EXTRA_RERANK_REQUEST_FORMAT = "rerank_request_format"

RERANK_REQUEST_FORMAT_FLAT = "flat"
RERANK_REQUEST_FORMAT_NESTED = "nested"

DEFAULT_RERANK_INSTRUCT = (
    "Given a web search query, retrieve relevant passages that answer the query."
)
