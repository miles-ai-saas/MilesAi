"""附件读字节逻辑。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.common.exceptions import BadRequestError
from app.tenant.attachments.services.attachment import AttachmentService


@pytest.mark.asyncio
async def test_read_image_bytes_rejects_non_image():
    tenant_id = uuid4()
    att_id = uuid4()
    ctx = MagicMock()
    ctx.tenant_id = tenant_id
    att = SimpleNamespace(
        id=att_id,
        tenant_id=tenant_id,
        filename="doc.pdf",
        mime_type="application/pdf",
        object_key="k",
        object_bucket="b",
    )

    db = MagicMock()
    svc = AttachmentService(db, ctx)
    svc._get_or_raise = AsyncMock(return_value=att)  # type: ignore[method-assign]

    with pytest.raises(BadRequestError, match="图片"):
        await svc.read_image_bytes(att_id)


@pytest.mark.asyncio
async def test_read_image_bytes_downloads():
    tenant_id = uuid4()
    att_id = uuid4()
    ctx = MagicMock()
    ctx.tenant_id = tenant_id
    att = SimpleNamespace(
        id=att_id,
        tenant_id=tenant_id,
        filename="a.png",
        mime_type="image/png",
        object_key="tenant/a.png",
        object_bucket="bucket",
    )

    db = MagicMock()
    svc = AttachmentService(db, ctx)
    svc._get_or_raise = AsyncMock(return_value=att)  # type: ignore[method-assign]

    with patch(
        "app.tenant.attachments.services.attachment.download_bytes",
        return_value=b"png-bytes",
    ):
        data, mime = await svc.read_image_bytes(att_id)

    assert data == b"png-bytes"
    assert mime == "image/png"
