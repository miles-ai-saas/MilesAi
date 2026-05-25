"""向量化 invoke_mode 与 ModelConfig.extra 键名。

invoke_mode：local | litellm | openai_compatible
extra：embedding_dimension、embedding_batch_size（通义默认上限 10）
"""

INVOKE_MODE_LOCAL = "local"
INVOKE_MODE_LITELLM = "litellm"
INVOKE_MODE_OPENAI_COMPATIBLE = "openai_compatible"

EXTRA_EMBEDDING_DIMENSION = "embedding_dimension"
EXTRA_INVOKE_MODE = "invoke_mode"
EXTRA_EMBEDDING_BATCH_SIZE = "embedding_batch_size"

# DashScope OpenAI 兼容 embeddings：单次 input 条数上限（见官方 InvalidParameter batch size）
DASHSCOPE_EMBEDDING_BATCH_SIZE_MAX = 10
