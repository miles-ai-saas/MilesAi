"""
向量化 Provider 实现包。

``registry`` 在 import 时注册：
- ``local`` → ``LocalEmbeddingProvider``（Sentence-Transformers）
- ``openai_compatible`` → ``OpenAICompatibleEmbeddingProvider``（HTTP /v1/embeddings）
- ``litellm`` → ``LiteLLMEmbeddingProvider``（``litellm.embedding``）
"""
