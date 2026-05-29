"""编译 + 运行、KB 入库编排的轻量集成测试（无 DB / 无 Celery / 无 LLM）。"""

from contextlib import contextmanager
from dataclasses import dataclass
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.flow_runtime.types import RunContext
from app.integrations.langgraph.compiler import run_compiled_canvas, validate_graph_for_compile
from app.models.kb import Document, DocumentStatus, KnowledgeBase
from app.tenant.kb.services.ingest import run_ingest

ECHO_GRAPH = {
    "nodes": [
        {"id": "in_1", "type": "TextInput", "data": {"type": "TextInput", "input_key": "query", "label": "输入"}},
        {"id": "out_1", "type": "TextOutput", "data": {"type": "TextOutput", "label": "输出"}},
    ],
    "edges": [
        {
            "id": "e1",
            "source": "in_1",
            "target": "out_1",
            "sourceHandle": "output",
            "targetHandle": "input",
        }
    ],
}

STATIC_GRAPH = {
    "nodes": [
        {"id": "in_1", "type": "TextInput", "data": {"type": "TextInput", "input_key": "query", "label": "输入"}},
        {
            "id": "static_1",
            "type": "StaticResponse",
            "data": {"type": "StaticResponse", "text": "收到：{{query}}", "label": "固定回复"},
        },
        {"id": "out_1", "type": "TextOutput", "data": {"type": "TextOutput", "label": "输出"}},
    ],
    "edges": [
        {
            "id": "e1",
            "source": "in_1",
            "target": "static_1",
            "sourceHandle": "output",
            "targetHandle": "query",
        },
        {
            "id": "e2",
            "source": "static_1",
            "target": "out_1",
            "sourceHandle": "output",
            "targetHandle": "input",
        },
    ],
}


@pytest.mark.asyncio
async def test_run_compiled_canvas_echoes_text_input():
    report = validate_graph_for_compile(ECHO_GRAPH)
    assert report.compilable is True

    ctx = RunContext(tenant_id=str(uuid4()), inputs={"query": "hello flow"})
    output, steps = await run_compiled_canvas(ECHO_GRAPH, ctx)

    assert output == "hello flow"
    assert steps[0]["type"] == "graph_start"
    assert any(s.get("node_type") == "TextInput" for s in steps if isinstance(s, dict))


@pytest.mark.asyncio
async def test_run_compiled_canvas_static_response_chain():
    report = validate_graph_for_compile(STATIC_GRAPH)
    assert report.compilable is True

    ctx = RunContext(tenant_id=str(uuid4()), inputs={"query": "集成测试"})
    output, steps = await run_compiled_canvas(STATIC_GRAPH, ctx)

    assert output == "收到：集成测试"
    assert any(s.get("node_type") == "StaticResponse" for s in steps if isinstance(s, dict))


def _sample_doc_kb(*, doc_id=None, kb_id=None, tenant_id=None):
    tid = tenant_id or uuid4()
    kid = kb_id or uuid4()
    did = doc_id or uuid4()
    embed_id = uuid4()
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
        embedding_model_config_id=embed_id,
        chunk_size=500,
        chunk_overlap=50,
    )
    return doc, kb


@dataclass
class _FakeIngestResult:
    chunk_count: int


def test_run_ingest_orchestration_marks_ready():
    doc, kb = _sample_doc_kb()
    db = MagicMock()

    def _get(model, pk):
        if model is Document and pk == doc.id:
            return doc
        if model is KnowledgeBase and pk == kb.id:
            return kb
        return None

    db.get.side_effect = _get

    @contextmanager
    def _fake_sync_db():
        yield db

    with (
        patch("app.tenant.kb.services.ingest.get_sync_db", _fake_sync_db),
        patch("app.tenant.kb.services.ingest.run_ingest_pipeline", return_value=_FakeIngestResult(chunk_count=2)) as pipeline,
    ):
        run_ingest(str(doc.id))

    assert doc.status == DocumentStatus.READY
    assert doc.fail_reason is None
    pipeline.assert_called_once()
    _, kwargs = pipeline.call_args
    assert kwargs["data"].filename == "note.txt"
    assert kwargs["data"].chunk_size == 500


def test_run_ingest_orchestration_persists_failure():
    doc, kb = _sample_doc_kb()
    db = MagicMock()

    def _get(model, pk):
        if model is Document and pk == doc.id:
            return doc
        if model is KnowledgeBase and pk == kb.id:
            return kb
        return None

    db.get.side_effect = _get

    @contextmanager
    def _fake_sync_db():
        yield db

    with (
        patch("app.tenant.kb.services.ingest.get_sync_db", _fake_sync_db),
        patch("app.tenant.kb.services.ingest.run_ingest_pipeline", side_effect=RuntimeError("embed failed")),
        patch("app.tenant.kb.services.ingest.persist_document_ingest_failure") as persist,
    ):
        with pytest.raises(RuntimeError, match="embed failed"):
            run_ingest(str(doc.id))

    persist.assert_called_once()
    assert persist.call_args.kwargs["phase"] == DocumentStatus.EMBEDDING
