"""CLIP 视觉向量化测试。"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import numpy as np
import pytest

from miles_ai.integrations.embeddings.constants import EXTRA_EMBEDDING_DIMENSION, INVOKE_MODE_CLIP
from miles_ai.integrations.embeddings.policy import ensure_clip_model
from miles_ai.integrations.embeddings.providers.clip import ClipEmbeddingProvider
from miles_core.models.model import ModelConfig
from miles_core.models.model.catalog import ModelCapabilityType


def _clip_model() -> ModelConfig:
    return ModelConfig(
        id=uuid4(),
        tenant_id=None,
        name="CLIP",
        provider="local",
        model_name="clip-ViT-B-32",
        model_type=ModelCapabilityType.EMBEDDING.value,
        extra={"invoke_mode": INVOKE_MODE_CLIP, EXTRA_EMBEDDING_DIMENSION: 512},
    )


def test_ensure_clip_model_rejects_text_embedding():
    model = _clip_model()
    model.extra = {"invoke_mode": "local", EXTRA_EMBEDDING_DIMENSION: 768}
    with pytest.raises(Exception, match="CLIP"):
        ensure_clip_model(model)


def test_clip_embed_texts():
    model = _clip_model()
    mock_encoder = MagicMock()
    mock_encoder.encode.return_value = np.array([[0.2] * 512], dtype=np.float32)
    with patch(
        "miles_ai.integrations.embeddings.providers.clip._load_clip",
        return_value=mock_encoder,
    ):
        vectors = ClipEmbeddingProvider().embed_texts(model, ["一只猫"])
    assert len(vectors) == 1
    assert len(vectors[0]) == 512
    mock_encoder.encode.assert_called_once()
