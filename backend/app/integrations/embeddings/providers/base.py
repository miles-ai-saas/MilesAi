"""
Embedding provider 协议（按 ``invoke_mode`` 注册）。

实现类
------
- ``LocalEmbeddingProvider``：进程内 / 本地服务
- ``OpenAICompatibleEmbeddingProvider``：OpenAI 兼容 ``/v1/embeddings``
- ``LiteLLMEmbeddingProvider``：多厂商统一入口

由 ``integrations.embeddings.registry`` 在 import 时注册。
"""

from __future__ import annotations

from typing import Protocol

from app.models.model import ModelConfig


class EmbeddingProvider(Protocol):
    """向量化后端实现协议（由 registry 按 invoke_mode 分发）。"""

    def embed_texts(self, model: ModelConfig, texts: list[str]) -> list[list[float]]:
        """把文本批量编码为向量（返回顺序与入参一致，空输入返回空列表）。"""
        ...
