"""rag.pipeline.ingest 单元测试。"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.rag.pipeline.ingest import IngestInput, run_ingest_pipeline


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

    with patch("app.rag.pipeline.ingest.upsert_chunk_vector", return_value="vec-1"):
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
