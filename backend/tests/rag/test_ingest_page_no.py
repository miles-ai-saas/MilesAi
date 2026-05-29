"""入库管道写入 page_no。"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from langchain_core.documents import Document

from app.rag.pipeline.ingest import IngestInput, run_ingest_pipeline


def test_ingest_sets_page_no_on_chunk_and_vector():
    doc = MagicMock()
    doc.id = uuid4()
    doc.tenant_id = uuid4()
    doc.kb_id = uuid4()

    kb = MagicMock()
    fake_docs = [
        Document(page_content="# A\n\nx", metadata={"parser": "docling", "page": 0}),
        Document(page_content="y", metadata={"parser": "docling", "page": 1}),
    ]

    db = MagicMock()
    added_chunks = []
    vector_calls = []

    def capture_add(obj):
        if hasattr(obj, "page_no"):
            added_chunks.append(obj)

    db.add.side_effect = capture_add

    def embed(_db, _kb, texts):
        return [[0.1] for _ in texts]

    with (
        patch(
            "app.rag.pipeline.ingest.load_documents_from_bytes",
            return_value=fake_docs,
        ),
        patch(
            "app.rag.pipeline.ingest.upsert_chunk_vector",
            side_effect=lambda **kw: vector_calls.append(kw) or "vec-1",
        ),
    ):
        result = run_ingest_pipeline(
            db,
            doc=doc,
            kb=kb,
            data=IngestInput(
                filename="f.pdf",
                mime_type="application/pdf",
                object_key="k",
                object_bucket="b",
                chunk_size=500,
                chunk_overlap=0,
            ),
            embed_texts=embed,
            load_bytes=lambda _k, _b: b"%PDF",
        )

    assert result.chunk_count >= 1
    assert any(c.page_no is not None for c in added_chunks)
    assert any(kw.get("page_no") is not None for kw in vector_calls)
