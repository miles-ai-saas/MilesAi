"""rag.pipeline.ingest 单元测试。"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from miles_ai.rag.pipeline.ingest import IngestInput, run_ingest_pipeline
from miles_core.models.kb import DocumentChunk


def _assign_chunk_ids_on_flush(db: MagicMock) -> None:
    """MagicMock Session 不会触发 ORM default；flush 时补齐 DocumentChunk.id。"""

    def flush():
        for call in db.add.call_args_list:
            obj = call.args[0]
            if isinstance(obj, DocumentChunk) and obj.id is None:
                obj.id = uuid4()

    db.flush.side_effect = flush


def test_run_ingest_pipeline_parses_and_chunks():
    doc = MagicMock()
    doc.id = uuid4()
    doc.tenant_id = uuid4()
    doc.kb_id = uuid4()

    kb = MagicMock()
    kb.chunk_size = 100
    kb.chunk_overlap = 10

    db = MagicMock()
    _assign_chunk_ids_on_flush(db)
    cleared: list = []

    def embed(_db, _kb, texts):
        return [[0.1, 0.2] for _ in texts]

    def load_bytes(key, bucket):
        assert key == "k/o"
        assert bucket == "bkt"
        return b"hello world " * 20

    def fake_upsert(items):
        return [f"vec-{i}" for i in range(len(items))]

    with patch("miles_ai.rag.pipeline.ingest.upsert_chunk_vectors", side_effect=fake_upsert):
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


def test_run_ingest_pipeline_upserts_vectors_in_one_batch():
    """分片向量应一次 upsert_chunk_vectors，条数等于 chunk 数。"""
    doc = MagicMock()
    doc.id = uuid4()
    doc.tenant_id = uuid4()
    doc.kb_id = uuid4()

    kb = MagicMock()
    db = MagicMock()
    _assign_chunk_ids_on_flush(db)

    def embed(_db, _kb, texts):
        return [[0.1, 0.2] for _ in texts]

    with patch(
        "miles_ai.rag.pipeline.ingest.upsert_chunk_vectors",
        side_effect=lambda items: [f"vec-{i}" for i in range(len(items))],
    ) as mock_upsert:
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
            load_bytes=lambda _k, _b: b"hello world " * 20,
        )

    mock_upsert.assert_called_once()
    writes = mock_upsert.call_args.args[0]
    assert len(writes) == result.chunk_count
    assert result.chunk_count >= 2
    db.flush.assert_called()


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
        patch(
            "miles_ai.rag.pipeline.ingest.upsert_chunk_vectors",
            side_effect=lambda items: [f"vec-{i}" for i in range(len(items))],
        ),
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


def test_run_ingest_pipeline_commits_after_clear_before_embed():
    """清旧 on_before_index 后须 commit，再调 embedding（释放长事务）。"""
    doc = MagicMock()
    doc.id = uuid4()
    doc.tenant_id = uuid4()
    doc.kb_id = uuid4()
    kb = MagicMock()
    db = MagicMock()
    _assign_chunk_ids_on_flush(db)
    order: list[str] = []

    def on_before(_session, _doc_id):
        order.append("clear")

    def embed(_db, _kb, texts):
        order.append("embed")
        return [[0.1, 0.2] for _ in texts]

    db.commit.side_effect = lambda: order.append("commit")

    with patch(
        "miles_ai.rag.pipeline.ingest.upsert_chunk_vectors",
        side_effect=lambda items: [f"vec-{i}" for i in range(len(items))],
    ):
        run_ingest_pipeline(
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
            raw=b"hello world " * 20,
            on_before_index=on_before,
        )

    assert order[:3] == ["clear", "commit", "embed"]


def test_run_ingest_pipeline_accepts_raw_without_load_bytes():
    """预加载 raw 时跳过 load_bytes（L1 会话外下载）。"""
    doc = MagicMock()
    doc.id = uuid4()
    doc.tenant_id = uuid4()
    doc.kb_id = uuid4()
    kb = MagicMock()
    db = MagicMock()
    _assign_chunk_ids_on_flush(db)
    load_called = False

    def load_bytes(_k, _b):
        nonlocal load_called
        load_called = True
        raise AssertionError("不应调用 load_bytes")

    with patch(
        "miles_ai.rag.pipeline.ingest.upsert_chunk_vectors",
        side_effect=lambda items: [f"vec-{i}" for i in range(len(items))],
    ):
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
            embed_texts=lambda _db, _kb, texts: [[0.1, 0.2] for _ in texts],
            raw=b"hello world " * 20,
            load_bytes=load_bytes,
        )

    assert result.chunk_count >= 1
    assert load_called is False


def test_run_ingest_pipeline_requires_raw_or_load_bytes():
    with pytest.raises(ValueError, match="raw 与 load_bytes"):
        run_ingest_pipeline(
            MagicMock(),
            doc=MagicMock(),
            kb=MagicMock(),
            data=IngestInput(
                filename="note.txt",
                mime_type="text/plain",
                object_key="k/o",
                object_bucket="bkt",
                chunk_size=50,
                chunk_overlap=5,
            ),
            embed_texts=lambda *_a, **_k: [],
        )
