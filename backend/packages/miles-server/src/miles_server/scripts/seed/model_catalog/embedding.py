"""内置向量化 / CLIP / 重排序模型条目。"""

from __future__ import annotations

from miles_common.constants.model_extra import EXTRA_INVOKE_MODE
from miles_core.models.model.catalog import ModelCapabilityType, ModelVendor
from miles_integrations.embeddings.constants import (
    EXTRA_EMBEDDING_BATCH_SIZE,
    EXTRA_EMBEDDING_DIMENSION,
    INVOKE_MODE_CLIP,
    INVOKE_MODE_LOCAL,
    INVOKE_MODE_OPENAI_COMPATIBLE,
)
from miles_integrations.rerank.constants import (
    EXTRA_RERANK_REQUEST_FORMAT,
    INVOKE_MODE_DASHSCOPE,
)

ENTRIES: list[dict] = [
# --- 向量化（知识库绑定）---
    {
        "model_code": "bge-base-zh-v1.5",
        "name": "本地 BGE 中文",
        "vendor": ModelVendor.OTHER.value,
        "provider": "local",
        "model_name": "BAAI/bge-base-zh-v1.5",
        "model_type": ModelCapabilityType.EMBEDDING.value,
        "description": "离线 Sentence-Transformers，无需 API Key，适合私有化默认知识库。",
        "context_window": "—",
        "sort_order": 1,
        "is_featured": True,
        "extra": {
            EXTRA_INVOKE_MODE: INVOKE_MODE_LOCAL,
            EXTRA_EMBEDDING_DIMENSION: 768,
        },
    },
    {
        "model_code": "qwen-text-embedding-v4",
        "name": "通义 text-embedding-v4",
        "vendor": ModelVendor.QWEN.value,
        "provider": "qwen",
        "model_name": "text-embedding-v4",
        "model_type": ModelCapabilityType.EMBEDDING.value,
        "description": "阿里云 DashScope 文本向量（Qwen3-Embedding），OpenAI 兼容接口；需在模型页配置 API Key。",
        "context_window": "—",
        "sort_order": 2,
        "is_featured": True,
        "extra": {
            EXTRA_INVOKE_MODE: INVOKE_MODE_OPENAI_COMPATIBLE,
            EXTRA_EMBEDDING_DIMENSION: 1024,
            EXTRA_EMBEDDING_BATCH_SIZE: 10,
        },
    },
    {
        "model_code": "clip-vit-b-32",
        "name": "本地 CLIP ViT-B-32",
        "vendor": ModelVendor.OTHER.value,
        "provider": "local",
        "model_name": "clip-ViT-B-32",
        "model_type": ModelCapabilityType.EMBEDDING.value,
        "description": "视觉相似度检索（以图搜图/文本搜图）；图片入库时写入 CLIP 向量。",
        "context_window": "—",
        "sort_order": 3,
        "is_featured": False,
        "extra": {
            EXTRA_INVOKE_MODE: INVOKE_MODE_CLIP,
            EXTRA_EMBEDDING_DIMENSION: 512,
        },
    },
    # --- 重排序（RAG 精排，模型页配置 API Key 后可用于测试）---
    {
        "model_code": "qwen3-rerank",
        "name": "通义 qwen3-rerank",
        "vendor": ModelVendor.QWEN.value,
        "provider": "qwen",
        "model_name": "qwen3-rerank",
        "model_type": ModelCapabilityType.RERANK.value,
        "description": "DashScope Qwen3 文本重排；使用 compatible-api/v1/reranks（flat 请求体）。",
        "context_window": "—",
        "sort_order": 3,
        "is_featured": True,
        "api_base": "https://dashscope.aliyuncs.com/compatible-api/v1",
        "extra": {
            EXTRA_INVOKE_MODE: INVOKE_MODE_OPENAI_COMPATIBLE,
        },
    },
    {
        "model_code": "gte-rerank-v2",
        "name": "通义 gte-rerank-v2",
        "vendor": ModelVendor.QWEN.value,
        "provider": "qwen",
        "model_name": "gte-rerank-v2",
        "model_type": ModelCapabilityType.RERANK.value,
        "description": "DashScope 经典文本重排模型，nested 请求格式；适合多语言语义检索。",
        "context_window": "—",
        "sort_order": 4,
        "is_featured": False,
        "api_base": "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank",
        "extra": {
            EXTRA_INVOKE_MODE: INVOKE_MODE_DASHSCOPE,
            EXTRA_RERANK_REQUEST_FORMAT: "nested",
        },
    },
]
