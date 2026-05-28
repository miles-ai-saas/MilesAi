"""知识库文档删除：清理向量、分片与对象存储。"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.kb import Document, DocumentStatus
from app.tenant.kb.services.kb import KnowledgeBaseService


@pytest.mark.asyncio
async def test_delete_document_clears_derived_and_object():
    ctx = MagicMock()
    ctx.tenant_id = uuid4()

    doc = Document(
        id=uuid4(),
        tenant_id=ctx.tenant_id,
        kb_id=uuid4(),
        filename="a.txt",
        mime_type="text/plain",
        file_size=10,
        object_bucket="b",
        object_key="tenant/kb/doc/a.txt",
        status=DocumentStatus.READY,
    )
    kb = MagicMock()
    kb.tenant_id = ctx.tenant_id
    kb.id = doc.kb_id

    db = AsyncMock()
    svc = KnowledgeBaseService(db, ctx)
    svc._get_kb_or_raise = AsyncMock(return_value=kb)
    svc.doc_repo.get_by_id_or_raise = AsyncMock(return_value=doc)

    storage = MagicMock()
    storage.storage.delete_object = MagicMock()

    with (
        patch(
            "app.tenant.kb.services.kb.documents.clear_document_derived_data_async",
            new_callable=AsyncMock,
        ) as mock_clear,
        patch(
            "app.tenant.kb.services.kb.documents.resolve_object_storage_async",
            new_callable=AsyncMock,
            return_value=storage,
        ),
        patch(
            "app.tenant.kb.services.kb.documents.mark_deleted",
            new_callable=AsyncMock,
        ) as mock_mark,
        patch(
            "app.tenant.kb.services.kb.documents.apply_storage_delta",
            new_callable=AsyncMock,
        ),
    ):
        await svc.delete_document(doc.kb_id, doc.id)

    mock_clear.assert_awaited_once_with(db, doc.id)
    storage.storage.delete_object.assert_called_once_with(doc.object_key, doc.object_bucket)
    mock_mark.assert_awaited_once()
