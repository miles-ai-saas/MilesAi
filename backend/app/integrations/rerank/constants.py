"""
Rerank ``invoke_mode`` 与 ``ModelConfig.extra`` 键名。

invoke_mode
-----------
- ``dashscope``：阿里云原生 text-rerank
- ``openai_compatible``：``/reranks`` 形状网关

``rerank_request_format``（仅 DashScope）
---------------------------------------
- ``flat`` / ``nested``，见 ``providers/dashscope._build_payload``
"""

INVOKE_MODE_DASHSCOPE = "dashscope"
INVOKE_MODE_OPENAI_COMPATIBLE = "openai_compatible"


EXTRA_RERANK_INSTRUCT = "rerank_instruct"
EXTRA_RERANK_REQUEST_FORMAT = "rerank_request_format"

RERANK_REQUEST_FORMAT_FLAT = "flat"
RERANK_REQUEST_FORMAT_NESTED = "nested"

DEFAULT_RERANK_INSTRUCT = "Given a web search query, retrieve relevant passages that answer the query."
