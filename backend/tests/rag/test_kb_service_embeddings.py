"""L1 kb 域向量化模块：ModelConfig 绑定在 L1 命名空间内完成。"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import numpy as np

from app.integrations.embeddings.constants import EXTRA_EMBEDDING_DIMENSION
from app.models.kb import KnowledgeBase
from app.models.model import ModelConfig
from app.models.model.catalog import ModelCapabilityType
from app.tenant.kb.services.embeddings import (
    build_kb_retrieval_bindings,
    embed_query_for_kb_sync,
)


def _local_bge_model() -> ModelConfig:
    return ModelConfig(
        id=uuid4(),
        tenant_id=None,
        name="本地 BGE 中文",
        provider="local",
        model_name="BAAI/bge-base-zh-v1.5",
        model_type=ModelCapabilityType.EMBEDDING.value,
        extra={"invoke_mode": "local", EXTRA_EMBEDDING_DIMENSION: 768},
    )


def test_embed_query_for_kb_sync_local():
    model = _local_bge_model()
    kb = KnowledgeBase(
        id=uuid4(),
        tenant_id=uuid4(),
        name="kb",
        embedding_model_config_id=model.id,
        embedding_dimension=768,
    )
    mock_encoder = MagicMock()
    mock_encoder.encode.return_value = np.array([[0.1] * 768], dtype=np.float32)
    db = MagicMock()
    with (
        patch(
            "app.tenant.kb.services.embeddings.resolve_embedding_model_sync",
            return_value=model,
        ),
        patch(
            "sentence_transformers.SentenceTransformer",
            return_value=mock_encoder,
        ),
    ):
        vec = embed_query_for_kb_sync(db, kb, "hello")
    assert len(vec) == 768


def test_build_kb_retrieval_bindings_shape():
    bindings = build_kb_retrieval_bindings()
    assert callable(bindings.embed_query_sync)
    assert callable(bindings.embed_query)
