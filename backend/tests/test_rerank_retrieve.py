"""RAG 检索 rerank 精排。"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.models.model import ModelConfig
from app.models.model_catalog import ModelCapabilityType, ModelVendor
from app.rag.retrieve.rerank import apply_rerank_to_hits, compute_rerank_fetch_limit


def _rerank_model() -> ModelConfig:
    return ModelConfig(
        id=uuid4(),
        tenant_id=None,
        name="qwen3-rerank",
        provider="qwen",
        model_name="qwen3-rerank",
        model_type=ModelCapabilityType.RERANK.value,
        vendor=ModelVendor.QWEN.value,
        api_key_encrypted="sk-test",
    )


def test_compute_rerank_fetch_limit_without_model():
    assert compute_rerank_fetch_limit(10, rerank_model=None) == 10


def test_compute_rerank_fetch_limit_with_model():
    assert compute_rerank_fetch_limit(10, rerank_model=_rerank_model(), candidate_k=50) == 30


def test_apply_rerank_to_hits_reorders_and_sets_score():
    hits = [
        {"chunk_id": "a", "content_preview": "doc-a", "score": 0.2},
        {"chunk_id": "b", "content_preview": "doc-b", "score": 0.9},
    ]
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "output": {"results": [{"index": 0, "relevance_score": 0.95}]}
    }

    with patch("httpx.post", return_value=mock_response):
        out = apply_rerank_to_hits(
            hits,
            query="q",
            rerank_model=_rerank_model(),
            top_n=1,
        )

    assert len(out) == 1
    assert out[0]["chunk_id"] == "a"
    assert out[0]["score_rerank"] == 0.95
