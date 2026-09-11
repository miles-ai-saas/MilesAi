"""混合检索：RRF 融合与检索模式解析。"""

from types import SimpleNamespace

from miles_ai.rag.retrieve import resolve_retrieval_mode, rrf_fuse


def test_rrf_fuse_merges_two_rankings():
    vec = [
        {"chunk_id": "a", "score": 0.9},
        {"chunk_id": "b", "score": 0.8},
    ]
    kw = [
        {"chunk_id": "b", "score": 0.95},
        {"chunk_id": "c", "score": 0.7},
    ]
    merged = rrf_fuse([vec, kw], limit=3)
    ids = [h["chunk_id"] for h in merged]
    assert "b" in ids
    assert len(merged) == 3
    assert merged[0]["score"] > 0


def test_resolve_retrieval_mode_default_uses_kb():
    kb = SimpleNamespace(retrieval_mode="hybrid")
    assert resolve_retrieval_mode(kb, "default") == "hybrid"


def test_resolve_retrieval_mode_request_override():
    kb = SimpleNamespace(retrieval_mode="vector")
    assert resolve_retrieval_mode(kb, "hybrid") == "hybrid"


def test_resolve_retrieval_mode_invalid_falls_back():
    kb = SimpleNamespace(retrieval_mode="unknown")
    assert resolve_retrieval_mode(kb, "default") == "vector"
