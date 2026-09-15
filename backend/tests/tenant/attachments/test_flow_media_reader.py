"""FlowMediaReader 定向单测：短会话装配、ctx 权限与 UUID 归一。

monkeypatch 打到 ``media_reader`` 模块命名空间（from-import 绑定），
用假 session 工厂与假 AttachmentService，不落真实 DB/对象存储。

会话来源是本文件的核心不变量：两个读方法都必须走 ``short_db_session``，全局
``AsyncSessionLocal`` 被换成「调用即炸」的替身。该读者在 Celery 里同样可达
（画布运行、定时智能体对话），回退全局会跨 loop 复用池内连接。
"""

import asyncio
from uuid import UUID, uuid4

from miles_core.models.media.reader import AttachmentBytes
from miles_portal.tenant.attachments.services import media_reader as media_reader_mod
from miles_portal.tenant.attachments.services.media_reader import (
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


def _boom(*args: object, **kwargs: object) -> None:
    """全局 ``AsyncSessionLocal`` 替身：被调用即炸。"""
    raise AssertionError("FlowMediaReader 不得用全局 AsyncSessionLocal（Worker 下跨 loop 复用连接必失败）")


def _install_fakes(monkeypatch):
    """装配假短会话工厂与假 service，返回 (session_calls, service_calls)。

    同时把全局 ``AsyncSessionLocal`` 换成「调用即炸」的替身：本文件所有用例因此
    都兼作「未回退全局」的护栏。
    """
    session_calls: list[object] = []
    service_calls: list[dict] = []

    def fake_short_db_session() -> _FakeSession:
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

    # raising=False：Step 4 前本模块只有 AsyncSessionLocal、Step 4 后只有 short_db_session，
    # 两个替换都要能装上，用例才会红在「走了哪个会话」而不是红在 monkeypatch 找不到属性。
    monkeypatch.setattr(media_reader_mod, "short_db_session", fake_short_db_session, raising=False)
    monkeypatch.setattr(media_reader_mod, "AsyncSessionLocal", _boom, raising=False)
    monkeypatch.setattr(media_reader_mod, "AttachmentService", FakeAttachmentService)
    return session_calls, service_calls


def test_module_does_not_reference_global_session_factory():
    """结构不变量：模块已不持有全局会话工厂，从源头排除回退全局的可能。"""
    assert not hasattr(media_reader_mod, "AsyncSessionLocal")


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
