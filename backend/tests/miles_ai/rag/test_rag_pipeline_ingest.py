"""rag.pipeline.ingest 单元测试。"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from miles_ai.rag.pipeline.ingest import IngestInput, run_ingest_pipeline


def test_run_ingest_pipeline_parses_and_chunks():
    doc = MagicMock()
    doc.id = uuid4()
    doc.tenant_id = uuid4()
    doc.kb_id = uuid4()

    kb = MagicMock()
    kb.chunk_size = 100
    kb.chunk_overlap = 10

    db = MagicMock()
    cleared: list = []

    def embed(_db, _kb, texts):
        return [[0.1, 0.2] for _ in texts]

    def load_bytes(key, bucket):
        assert key == "k/o"
        assert bucket == "bkt"
        return b"hello world " * 20

    with patch("miles_ai.rag.pipeline.ingest.upsert_chunk_vector", return_value="vec-1"):
        result = run_ingest_pipeline(
            db,
            doc=doc,
            kb=kb,
            data=IngestInput(
                filename="note.txt",
                mime_type="text/plain",
                object_key="k/o",
                object_bucket="bkt",
                chunk_size=50,
                chunk_overlap=5,
            ),
            embed_texts=embed,
            load_bytes=load_bytes,
            on_before_index=lambda session, doc_id: cleared.append(doc_id),
        )

    assert result.chunk_count >= 1
    assert cleared == [doc.id]
    assert db.add.called


def test_run_ingest_pipeline_rejects_vector_count_mismatch():
    """embedding 返回的向量数少于分片数时必须报错，而非静默漏写分片。"""
    doc = MagicMock()
    doc.id = uuid4()
    doc.tenant_id = uuid4()
    doc.kb_id = uuid4()

    kb = MagicMock()
    kb.chunk_size = 50
    kb.chunk_overlap = 0

    def embed(_db, _kb, texts):
        # 故意少返回一个向量（模拟 embedding 服务截断/丢包）
        return [[0.1, 0.2] for _ in texts[:-1]]

    with (
        patch("miles_ai.rag.pipeline.ingest.upsert_chunk_vector", return_value="vec-1"),
        pytest.raises(ValueError, match="shorter than"),
    ):
        run_ingest_pipeline(
            MagicMock(),
            doc=doc,
            kb=kb,
            data=IngestInput(
                filename="note.txt",
                mime_type="text/plain",
                object_key="k/o",
                object_bucket="bkt",
                chunk_size=50,
                chunk_overlap=0,
            ),
            embed_texts=embed,
            load_bytes=lambda _key, _bucket: b"hello world " * 20,
        )
