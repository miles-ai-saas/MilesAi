"""租户附件上传与删除。"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.tenant.attachments.services.attachment import AttachmentService


@pytest.mark.asyncio
async def test_upload_attachment_stores_object_and_updates_quota():
    tenant_id = uuid4()
    user_id = uuid4()
    ctx = MagicMock()
    ctx.tenant_id = tenant_id
    ctx.user_id = user_id

    file = MagicMock()
    file.filename = "note.txt"
    file.content_type = "text/plain"
    file.read = AsyncMock(return_value=b"hello")

    att_id = uuid4()
    now = datetime.now(timezone.utc)
    created = SimpleNamespace(
        id=att_id,
        tenant_id=tenant_id,
        uploaded_by=user_id,
        filename="note.txt",
        mime_type="text/plain",
        file_size=5,
        object_bucket="bucket",
        object_key="pending",
        purpose="general",
        resource_type=None,
        resource_id=None,
        created_at=now,
    )

    db = AsyncMock()
    svc = AttachmentService(db, ctx)
    svc.repo = MagicMock()
    svc.repo.create = AsyncMock(return_value=created)

    from app.tenant.attachments.schemas.attachment import AttachmentUploadMeta

    meta = AttachmentUploadMeta()

    with (
        patch(
            "app.tenant.attachments.services.attachment.assert_can_upload_bytes",
            new_callable=AsyncMock,
        ),
        patch("app.tenant.attachments.services.attachment.upload_bytes"),
        patch(
            "app.tenant.attachments.services.attachment.apply_storage_delta",
            new_callable=AsyncMock,
        ),
    ):
        out = await svc.upload(file, meta)

    svc.repo.create.assert_awaited_once()
    assert created.object_key.endswith("note.txt")
    assert out.id == att_id
