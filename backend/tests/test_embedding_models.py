"""知识库向量化：ModelConfig 绑定与运行时。"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import numpy as np
import pytest

from app.ai_stack.embeddings.runtime import (
    EXTRA_EMBEDDING_DIMENSION,
    build_embeddings,
    embedding_dimension_from_model,
)
from app.ai_stack.langchain.embeddings import embed_query_for_kb_sync
from app.models.kb import KnowledgeBase
from app.models.model import ModelConfig
from app.models.model_catalog import ModelCapabilityType
from app.tenant.kb.schemas.kb import KnowledgeBaseUpdate


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


def test_embedding_dimension_from_model():
    assert embedding_dimension_from_model(_local_bge_model()) == 768


def test_kb_update_rejects_embedding_change():
    with pytest.raises(ValueError, match="向量化模型"):
        KnowledgeBaseUpdate(embedding_model_config_id=uuid4())


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
            "app.ai_stack.langchain.embeddings.resolve_embedding_model_sync",
            return_value=model,
        ),
        patch(
            "sentence_transformers.SentenceTransformer",
            return_value=mock_encoder,
        ),
    ):
        vec = embed_query_for_kb_sync(db, kb, "hello")

    assert len(vec) == 768
    emb = build_embeddings(model)
    assert emb.__class__.__name__ == "ModelConfigEmbeddings"
