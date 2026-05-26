"""
向量化 ``invoke_mode`` 与 ``ModelConfig.extra`` 键名常量。

invoke_mode
-----------
- ``local``：本地/内网 embedding 服务，无需 API Key
- ``openai_compatible``：OpenAI 兼容 REST（含 DashScope 兼容端点）
- ``litellm``：经 LiteLLM 统一多厂商

extra 键
--------
- ``embedding_dimension``：向量维度，创建 KB 时固化
- ``embedding_batch_size``：批量 embed 条数上限；通义见 ``DASHSCOPE_EMBEDDING_BATCH_SIZE_MAX``
"""

INVOKE_MODE_LOCAL = "local"
INVOKE_MODE_LITELLM = "litellm"
INVOKE_MODE_OPENAI_COMPATIBLE = "openai_compatible"

from app.common.constants.model_extra import EXTRA_INVOKE_MODE

EXTRA_EMBEDDING_DIMENSION = "embedding_dimension"
EXTRA_EMBEDDING_BATCH_SIZE = "embedding_batch_size"

# DashScope OpenAI 兼容 embeddings：单次 input 条数上限（见官方 InvalidParameter batch size）
DASHSCOPE_EMBEDDING_BATCH_SIZE_MAX = 10
