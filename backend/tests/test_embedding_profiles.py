"""知识库向量化规格。"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import numpy as np
import pytest

from app.ai_stack.embedding_profiles import get_embedding_profile
from app.ai_stack.langchain.embeddings import get_embeddings_for_kb
from app.models.kb import KnowledgeBase
from app.tenant.kb.schemas.kb import KnowledgeBaseUpdate


def test_get_embedding_profile():
    spec = get_embedding_profile("local-minilm")
    assert spec.dimension == 384
    assert spec.backend == "local"


def test_kb_update_rejects_embedding_change():
    with pytest.raises(ValueError, match="向量化规格"):
        KnowledgeBaseUpdate(embedding_profile="dashscope-v3")


def test_get_embeddings_for_kb_local():
    kb = KnowledgeBase(
        id=uuid4(),
        tenant_id=uuid4(),
        name="test-kb",
        embedding_profile="local-minilm",
        embedding_backend="local",
        embedding_model_name="sentence-transformers/all-MiniLM-L6-v2",
        embedding_dimension=384,
    )
    mock_encoder = MagicMock()
    mock_encoder.encode.return_value = np.array([[0.1] * 384], dtype=np.float32)

    with patch(
        "sentence_transformers.SentenceTransformer",
        return_value=mock_encoder,
    ):
        emb = get_embeddings_for_kb(kb)
        vec = emb.embed_query("hello")

    assert len(vec) == 384
    mock_encoder.encode.assert_called_once()
