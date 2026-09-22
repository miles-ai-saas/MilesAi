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


def _patch_storage_download(raw: bytes = b"hello world " * 20):
    storage = MagicMock()
    storage.download_bytes.return_value = raw
    resolved = MagicMock(storage=storage)
    return patch(
        "miles_portal.tenant.kb.services.ingest.resolve_object_storage_sync",
        return_value=resolved,
    )


def test_run_ingest_commits_parsing_and_embedding_before_pipeline():
    doc, kb = _sample_doc_kb()
    fake_sync_db, entries = _tracking_sync_db_factory(doc, kb)
    statuses_committed_before_pipeline: list[DocumentStatus] = []

    def _pipeline(*_args, **_kwargs):
        statuses_committed_before_pipeline[:] = [
            e["status_on_exit"] for e in entries if e["committed"]
        ]
        assert _kwargs.get("raw") is not None
        assert _kwargs.get("load_bytes") is None
        return MagicMock(chunk_count=1)

    with (
        patch("miles_portal.tenant.kb.services.ingest.get_sync_db", fake_sync_db),
        _patch_storage_download(),
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
        _patch_storage_download(),
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

    # PARSING + resolve storage + EMBEDDING + pipeline(失败回滚) + 失败会话
    assert len(entries) >= 4
    assert entries[-1]["committed"] is True
    assert len(persist_db_ids) == 1
    assert persist_db_ids[0] == entries[-1]["db_id"]
    assert persist_db_ids[0] not in pipeline_db_ids


def test_run_ingest_empty_text_fails_as_parsing():
    """会话外 parse 空文本须以 phase=PARSING 失败（PARSE_FAILED），不得进 EMBEDDING。"""
    doc, kb = _sample_doc_kb()
    fake_sync_db, entries = _tracking_sync_db_factory(doc, kb)
    phases: list[DocumentStatus] = []

    def _persist(_db, _doc, *, phase, exc):
        phases.append(phase)
        assert "未能提取有效文本" in str(exc)

    with (
        patch("miles_portal.tenant.kb.services.ingest.get_sync_db", fake_sync_db),
        _patch_storage_download(raw=b"   \n\t  "),
        patch(
            "miles_portal.tenant.kb.services.ingest.run_ingest_pipeline",
            side_effect=AssertionError("空文本不应进入 pipeline"),
        ),
        patch(
            "miles_portal.tenant.kb.services.ingest.persist_document_ingest_failure",
            side_effect=_persist,
        ),
    ):
        with pytest.raises(ValueError, match="未能提取有效文本"):
            run_ingest(str(doc.id))

    assert phases == [DocumentStatus.PARSING]
    assert DocumentStatus.EMBEDDING not in [e["status_on_exit"] for e in entries if e["committed"]]


def test_run_ingest_download_failure_stays_parsing():
    """S3 下载失败发生在 EMBEDDING 之前，phase 保持 PARSING。"""
    doc, kb = _sample_doc_kb()
    fake_sync_db, _entries = _tracking_sync_db_factory(doc, kb)
    phases: list[DocumentStatus] = []

    storage = MagicMock()
    storage.download_bytes.side_effect = RuntimeError("s3 down")
    resolved = MagicMock(storage=storage)

    def _persist(_db, _doc, *, phase, exc):
        phases.append(phase)
        assert "s3 down" in str(exc)

    with (
        patch("miles_portal.tenant.kb.services.ingest.get_sync_db", fake_sync_db),
        patch(
            "miles_portal.tenant.kb.services.ingest.resolve_object_storage_sync",
            return_value=resolved,
        ),
        patch(
            "miles_portal.tenant.kb.services.ingest.persist_document_ingest_failure",
            side_effect=_persist,
        ),
    ):
        with pytest.raises(RuntimeError, match="s3 down"):
            run_ingest(str(doc.id))

    assert phases == [DocumentStatus.PARSING]


def test_run_ingest_kb_missing_after_parsing_persists_failure():
    """PARSING 已提交后若 KB 消失，须 persist 失败态，不得静默 return 导致永久卡住。"""
    doc, kb = _sample_doc_kb()
    phases: list[DocumentStatus] = []
    entries: list[dict] = []

    def _get(model, pk):
        if model is Document and pk == doc.id:
            return doc
        if model is KnowledgeBase and pk == kb.id:
            # 首段会话内仍可见；PARSING 提交后（status 已是 PARSING）再取则视为删除
            if doc.status == DocumentStatus.PARSING:
                return None
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

    def _persist(_db, _doc, *, phase, exc):
        phases.append(phase)
        assert "知识库不存在或已删除" in str(exc)

    with (
        patch("miles_portal.tenant.kb.services.ingest.get_sync_db", _fake_sync_db),
        _patch_storage_download(),
        patch(
            "miles_portal.tenant.kb.services.ingest.run_ingest_pipeline",
            side_effect=AssertionError("KB 已消失不应进入 pipeline"),
        ),
        patch(
            "miles_portal.tenant.kb.services.ingest.persist_document_ingest_failure",
            side_effect=_persist,
        ),
    ):
        with pytest.raises(ValueError, match="知识库不存在或已删除"):
            run_ingest(str(doc.id))

    assert phases == [DocumentStatus.PARSING]
    assert DocumentStatus.PARSING in [e["status_on_exit"] for e in entries if e["committed"]]
