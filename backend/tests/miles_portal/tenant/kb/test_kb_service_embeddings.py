"""L1 kb 域向量化模块：ModelConfig 绑定在 L1 命名空间内完成。"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import numpy as np

from miles_core.models.kb import KnowledgeBase
from miles_core.models.model import ModelConfig
from miles_core.models.model.catalog import ModelCapabilityType
from miles_integrations.embeddings.constants import EXTRA_EMBEDDING_DIMENSION, INVOKE_MODE_CLIP
from miles_portal.tenant.kb.services.embeddings import (
    build_kb_retrieval_bindings,
    embed_image_chunks_vectors_sync,
    embed_query_for_kb_sync,
    embed_texts_for_kb_sync,
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
            "miles_portal.tenant.kb.services.embeddings.resolve_embedding_model_sync",
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


def test_embed_texts_for_kb_sync_commits_before_embed_documents():
    """resolve 后须 commit，再调厂商 embed_documents，避免 HTTP 占会话。"""
    model = _local_bge_model()
    kb = KnowledgeBase(
        id=uuid4(),
        tenant_id=uuid4(),
        name="kb",
        embedding_model_config_id=model.id,
        embedding_dimension=768,
    )
    db = MagicMock()
    order: list[str] = []
    db.commit.side_effect = lambda: order.append("commit")

    emb = MagicMock()
    emb.embed_documents.side_effect = lambda texts: (order.append("embed"), [[0.1] * 768])[1]

    with (
        patch(
            "miles_portal.tenant.kb.services.embeddings.resolve_embedding_model_sync",
            return_value=model,
        ),
        patch(
            "miles_portal.tenant.kb.services.embeddings.build_embeddings",
            return_value=emb,
        ),
    ):
        vecs = embed_texts_for_kb_sync(db, kb, ["hello"])

    assert order == ["commit", "embed"]
    assert len(vecs) == 1
    db.commit.assert_called_once()


def test_embed_image_chunks_vectors_sync_commits_before_clip():
    """CLIP 路径：resolve 后 commit，再调 embed_images。"""
    model = ModelConfig(
        id=uuid4(),
        tenant_id=None,
        name="CLIP",
        provider="openai",
        model_name="clip",
        model_type=ModelCapabilityType.EMBEDDING.value,
        extra={"invoke_mode": INVOKE_MODE_CLIP, EXTRA_EMBEDDING_DIMENSION: 512},
    )
    kb = KnowledgeBase(
        id=uuid4(),
        tenant_id=uuid4(),
        name="kb",
        embedding_model_config_id=uuid4(),
        visual_embedding_model_config_id=model.id,
        embedding_dimension=768,
    )
    db = MagicMock()
    order: list[str] = []
    db.commit.side_effect = lambda: order.append("commit")

    provider = MagicMock()
    provider.embed_images.side_effect = lambda m, imgs: (
        order.append("clip"),
        [[0.2] * 512],
    )[1]

    with (
        patch(
            "miles_portal.tenant.kb.services.embeddings.resolve_embedding_model_sync",
            return_value=model,
        ),
        patch(
            "miles_portal.tenant.kb.services.embeddings.get_embedding_provider",
            return_value=provider,
        ),
        patch("miles_portal.tenant.kb.services.embeddings._ensure_clip"),
    ):
        vecs = embed_image_chunks_vectors_sync(db, kb, b"img", chunk_count=2)

    assert order == ["commit", "clip"]
    assert len(vecs) == 2
    db.commit.assert_called_once()
