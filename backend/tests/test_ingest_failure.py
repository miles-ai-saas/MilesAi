"""文档入库失败状态须 commit，避免 rollback 后仍显示处理中。"""

from unittest.mock import MagicMock
from uuid import uuid4

from app.models.kb import Document, DocumentStatus
from app.tenant.kb.services.ingest_failure import persist_document_ingest_failure


def test_persist_document_ingest_failure_commits_embed_failed():
    doc = Document(
        id=uuid4(),
        tenant_id=uuid4(),
        kb_id=uuid4(),
        filename="a.pdf",
        mime_type="application/pdf",
        file_size=1,
        object_bucket="b",
        object_key="k",
        status=DocumentStatus.EMBEDDING,
    )
    db = MagicMock()
    persist_document_ingest_failure(
        db,
        doc,
        phase=DocumentStatus.EMBEDDING,
        exc=RuntimeError("向量化失败: batch size"),
    )
    assert doc.status == DocumentStatus.EMBED_FAILED
    assert "向量化失败" in (doc.fail_reason or "")
    db.flush.assert_called_once()
    db.commit.assert_called_once()


def test_persist_document_ingest_failure_parse_phase():
    doc = Document(
        id=uuid4(),
        tenant_id=uuid4(),
        kb_id=uuid4(),
        filename="a.pdf",
        mime_type="application/pdf",
        file_size=1,
        object_bucket="b",
        object_key="k",
        status=DocumentStatus.PARSING,
    )
    db = MagicMock()
    persist_document_ingest_failure(db, doc, phase=DocumentStatus.PARSING, exc=ValueError("未能提取有效文本"))
    assert doc.status == DocumentStatus.PARSE_FAILED
    db.commit.assert_called_once()
