"""AttachmentService.read_attachment_bytes 定向单测。

直接构造 service（FakeDb + TenantContext），monkeypatch 对象存储解析与
``_get_or_raise``，覆盖 mime 兜底与 pending 未就绪分支。
"""

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from miles_common.exceptions import BadRequestError
from miles_core.tenant import TenantContext
from miles_portal.tenant.attachments.services import attachment as attachment_mod
from miles_portal.tenant.attachments.services.attachment import AttachmentService


def _ctx(tenant_id) -> TenantContext:
    return TenantContext(
        user_id=uuid4(),
        tenant_id=tenant_id,
        username="tester",
        is_superuser=False,
        permissions=frozenset(["attachment:read"]),
    )


def _install(monkeypatch, att: SimpleNamespace):
    async def fake_resolve_object_storage_async(tenant_id, db):
        return SimpleNamespace(storage=SimpleNamespace(download_bytes=lambda key, bucket: b"raw"))

    async def fake_get_or_raise(self, attachment_id):
        return att

    monkeypatch.setattr(attachment_mod, "resolve_object_storage_async", fake_resolve_object_storage_async)
    monkeypatch.setattr(AttachmentService, "_get_or_raise", fake_get_or_raise)


def test_read_attachment_bytes_returns_data_mime_filename(monkeypatch):
    tenant_id = uuid4()
    att = SimpleNamespace(
        tenant_id=tenant_id,
        object_key="k",
        object_bucket=None,
        mime_type="audio/mpeg",
        filename="a.mp3",
    )
    _install(monkeypatch, att)

    service = AttachmentService(object(), _ctx(tenant_id))
    out = asyncio.run(service.read_attachment_bytes(uuid4()))

    assert out == (b"raw", "audio/mpeg", "a.mp3")


def test_read_attachment_bytes_defaults_missing_mime(monkeypatch):
    tenant_id = uuid4()
    att = SimpleNamespace(
        tenant_id=tenant_id,
        object_key="k",
        object_bucket=None,
        mime_type=None,
        filename="a.bin",
    )
    _install(monkeypatch, att)

    service = AttachmentService(object(), _ctx(tenant_id))
    _data, mime, _filename = asyncio.run(service.read_attachment_bytes(uuid4()))

    assert mime == "application/octet-stream"


def test_read_attachment_bytes_raises_when_pending(monkeypatch):
    tenant_id = uuid4()
    att = SimpleNamespace(
        tenant_id=tenant_id,
        object_key="pending",
        object_bucket=None,
        mime_type="audio/mpeg",
        filename="a.mp3",
    )
    _install(monkeypatch, att)

    service = AttachmentService(object(), _ctx(tenant_id))
    with pytest.raises(BadRequestError, match="未就绪"):
        asyncio.run(service.read_attachment_bytes(uuid4()))
