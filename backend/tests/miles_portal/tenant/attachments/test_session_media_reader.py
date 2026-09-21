"""SessionMediaReader：复用调用方会话的媒体读取器。"""

import asyncio
from uuid import uuid4

from miles_core.models.media.reader import AttachmentBytes
from miles_core.tenant import TenantContext
from miles_portal.tenant.attachments.services import media_reader as mod


def _run(coro):
    return asyncio.run(coro)


def _ctx() -> TenantContext:
    return TenantContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        username="session-media",
        is_superuser=False,
        permissions=frozenset(["attachment:read"]),
    )


def test_session_reader_reads_image_with_caller_session(monkeypatch):
    calls: list[object] = []

    class FakeService:
        def __init__(self, db, ctx):
            calls.append((db, ctx))

        async def read_image_bytes(self, attachment_id):
            return b"IMG", "image/png"

    monkeypatch.setattr(mod, "AttachmentService", FakeService)
    db, ctx = object(), _ctx()
    att = mod.build_session_media_reader(db, ctx).read_image_bytes(uuid4())
    out = _run(att)
    assert out == AttachmentBytes(data=b"IMG", mime="image/png", filename=None)
    # 复用调用方会话/上下文，未新开 session
    assert calls[0][0] is db and calls[0][1] is ctx


def test_session_reader_reads_attachment_with_filename(monkeypatch):
    class FakeService:
        def __init__(self, db, ctx):
            pass

        async def read_attachment_bytes(self, attachment_id):
            return b"AUD", "audio/mpeg", "a.mp3"

    monkeypatch.setattr(mod, "AttachmentService", FakeService)
    att = mod.build_session_media_reader(object(), _ctx()).read_attachment_bytes(uuid4())
    out = _run(att)
    assert out == AttachmentBytes(data=b"AUD", mime="audio/mpeg", filename="a.mp3")
