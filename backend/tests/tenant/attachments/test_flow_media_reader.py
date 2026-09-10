"""FlowMediaReader 定向单测：短会话装配、ctx 权限与 UUID 归一。

monkeypatch 打到 ``media_reader`` 模块命名空间（from-import 绑定），
用假 session 工厂与假 AttachmentService，不落真实 DB/对象存储。
"""

import asyncio
from uuid import UUID, uuid4

from app.models.media.reader import AttachmentBytes
from app.tenant.attachments.services import media_reader as media_reader_mod
from app.tenant.attachments.services.media_reader import (
    FlowMediaReader,
    build_flow_media_reader,
)


class _FakeSession:
    def __init__(self, db: object) -> None:
        self._db = db

    async def __aenter__(self) -> object:
        return self._db

    async def __aexit__(self, *exc: object) -> None:
        return None


def _install_fakes(monkeypatch):
    """装配假 session 工厂与假 service，返回 (session_calls, service_calls)。"""
    session_calls: list[object] = []
    service_calls: list[dict] = []

    def fake_async_session_local() -> _FakeSession:
        db = object()
        session_calls.append(db)
        return _FakeSession(db)

    class FakeAttachmentService:
        def __init__(self, db, ctx) -> None:
            service_calls.append({"db": db, "ctx": ctx})

        async def read_image_bytes(self, attachment_id):
            return b"img", "image/png"

        async def read_attachment_bytes(self, attachment_id):
            return b"aud", "audio/mpeg", "a.mp3"

    monkeypatch.setattr(media_reader_mod, "AsyncSessionLocal", fake_async_session_local)
    monkeypatch.setattr(media_reader_mod, "AttachmentService", FakeAttachmentService)
    return session_calls, service_calls


def test_read_image_bytes_returns_bytes_and_builds_ctx(monkeypatch):
    session_calls, service_calls = _install_fakes(monkeypatch)
    tenant_id, user_id = uuid4(), uuid4()

    reader = FlowMediaReader(tenant_id=tenant_id, user_id=user_id)
    out = asyncio.run(reader.read_image_bytes(uuid4()))

    assert out == AttachmentBytes(data=b"img", mime="image/png", filename=None)
    assert len(session_calls) == 1
    assert len(service_calls) == 1
    ctx = service_calls[0]["ctx"]
    assert ctx.tenant_id == tenant_id
    assert ctx.user_id == user_id
    assert ctx.username == "flow_media"
    assert ctx.permissions == frozenset({"attachment:read"})
    assert ctx.is_superuser is False


def test_read_attachment_bytes_returns_filename_and_mime(monkeypatch):
    _install_fakes(monkeypatch)

    reader = FlowMediaReader(tenant_id=uuid4(), user_id=uuid4())
    out = asyncio.run(reader.read_attachment_bytes(uuid4()))

    assert out.data == b"aud"
    assert out.mime == "audio/mpeg"
    assert out.filename == "a.mp3"


def test_build_flow_media_reader_parses_str_ids(monkeypatch):
    _install_fakes(monkeypatch)
    tenant_id, user_id = uuid4(), uuid4()

    reader = build_flow_media_reader(tenant_id=str(tenant_id), user_id=str(user_id))
    asyncio.run(reader.read_image_bytes(uuid4()))

    assert isinstance(reader._tenant_id, UUID)
    assert isinstance(reader._user_id, UUID)
    assert reader._tenant_id == tenant_id
    assert reader._user_id == user_id

    anon = build_flow_media_reader(tenant_id=str(tenant_id), user_id=None)
    asyncio.run(anon.read_image_bytes(uuid4()))

    assert anon._user_id is None


def test_anonymous_reader_ctx_has_none_user_id(monkeypatch):
    _session_calls, service_calls = _install_fakes(monkeypatch)

    reader = build_flow_media_reader(tenant_id=str(uuid4()), user_id=None)
    asyncio.run(reader.read_image_bytes(uuid4()))

    ctx = service_calls[-1]["ctx"]
    assert ctx.user_id is None


def test_each_read_opens_new_session(monkeypatch):
    session_calls, _service_calls = _install_fakes(monkeypatch)
    reader = FlowMediaReader(tenant_id=uuid4(), user_id=uuid4())

    async def _run():
        await reader.read_image_bytes(uuid4())
        await reader.read_image_bytes(uuid4())
        await reader.read_attachment_bytes(uuid4())

    asyncio.run(_run())

    assert len(session_calls) == 3
