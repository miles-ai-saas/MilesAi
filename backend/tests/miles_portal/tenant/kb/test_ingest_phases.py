"""run_ingest 分阶段 commit：PARSING/EMBEDDING 须在 pipeline 前可见；失败用独立会话。"""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from miles_core.models.kb import Document, DocumentStatus, KnowledgeBase
from miles_portal.tenant.kb.services.ingest import run_ingest


def _sample_doc_kb():
    tid = uuid4()
    kid = uuid4()
    did = uuid4()
    doc = Document(
        id=did,
        tenant_id=tid,
        kb_id=kid,
        filename="note.txt",
        mime_type="text/plain",
        file_size=12,
        object_bucket="test-bucket",
        object_key="kb/note.txt",
        status=DocumentStatus.PENDING,
    )
    kb = KnowledgeBase(
        id=kid,
        tenant_id=tid,
        name="测试库",
        embedding_model_config_id=uuid4(),
        chunk_size=500,
        chunk_overlap=50,
    )
    return doc, kb


def _tracking_sync_db_factory(doc: Document, kb: KnowledgeBase):
    """可记录每次进入 get_sync_db 时的文档状态快照。"""
    entries: list[dict] = []

    def _get(model, pk):
        if model is Document and pk == doc.id:
            return doc
        if model is KnowledgeBase and pk == kb.id:
            return kb
        return None

    @contextmanager
    def _fake_sync_db():
        db = MagicMock()
        db.get.side_effect = _get
        entry = {
            "db_id": id(db),
            "status_on_enter": doc.status,
            "status_on_exit": None,
            "committed": False,
        }
        entries.append(entry)
        try:
            yield db
            entry["status_on_exit"] = doc.status
            entry["committed"] = True
        except Exception:
            entry["status_on_exit"] = doc.status
            entry["committed"] = False
            raise

    return _fake_sync_db, entries


def test_run_ingest_commits_parsing_and_embedding_before_pipeline():
    doc, kb = _sample_doc_kb()
    fake_sync_db, entries = _tracking_sync_db_factory(doc, kb)
    statuses_committed_before_pipeline: list[DocumentStatus] = []

    def _pipeline(*_args, **_kwargs):
        statuses_committed_before_pipeline[:] = [
            e["status_on_exit"] for e in entries if e["committed"]
        ]
        return MagicMock(chunk_count=1)

    with (
        patch("miles_portal.tenant.kb.services.ingest.get_sync_db", fake_sync_db),
        patch(
            "miles_portal.tenant.kb.services.ingest.run_ingest_pipeline",
            side_effect=_pipeline,
        ),
    ):
        run_ingest(str(doc.id))

    assert DocumentStatus.PARSING in statuses_committed_before_pipeline
    assert DocumentStatus.EMBEDDING in statuses_committed_before_pipeline
    assert len(statuses_committed_before_pipeline) >= 2
    assert doc.status == DocumentStatus.READY


def test_run_ingest_failure_uses_fresh_session_for_persist():
    doc, kb = _sample_doc_kb()
    fake_sync_db, entries = _tracking_sync_db_factory(doc, kb)
    persist_db_ids: list[int] = []
    pipeline_db_ids: list[int] = []

    def _pipeline(db, *_args, **_kwargs):
        pipeline_db_ids.append(id(db))
        raise RuntimeError("embed failed")

    def _persist(db, _doc, *, phase, exc):
        persist_db_ids.append(id(db))
        assert phase == DocumentStatus.EMBEDDING
        assert "embed failed" in str(exc)

    with (
        patch("miles_portal.tenant.kb.services.ingest.get_sync_db", fake_sync_db),
        patch(
            "miles_portal.tenant.kb.services.ingest.run_ingest_pipeline",
            side_effect=_pipeline,
        ),
        patch(
            "miles_portal.tenant.kb.services.ingest.persist_document_ingest_failure",
            side_effect=_persist,
        ),
    ):
        with pytest.raises(RuntimeError, match="embed failed"):
            run_ingest(str(doc.id))

    # PARSING + EMBEDDING + pipeline(失败回滚) + 失败会话
    assert len(entries) >= 4
    assert entries[-1]["committed"] is True
    assert len(persist_db_ids) == 1
    assert persist_db_ids[0] == entries[-1]["db_id"]
    assert persist_db_ids[0] not in pipeline_db_ids
