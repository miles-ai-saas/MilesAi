"""scan_words_loader 定向单测：短会话委托与 tenant 解析。

monkeypatch 均打到 ``scan_words_loader`` 模块命名空间（from-import 绑定），
short_db_session 用假 async 上下文管理器替换，不落真实 DB。
"""

import asyncio
from uuid import uuid4

from miles_core.models.compliance.constants import SensitiveAction
from miles_portal.tenant.compliance.services import scan_words_loader as loader_mod
from miles_portal.tenant.compliance.services.scan_words_loader import build_scan_words_loader


class _FakeSessionCtx:
    """假 short_db_session：__aenter__ 返回假 db，__aexit__ 返回 None。"""

    def __init__(self, db):
        self._db = db

    async def __aenter__(self):
        return self._db

    async def __aexit__(self, exc_type, exc, tb):
        return None


class _Boom:
    """全局会话替身：被调用即失败，用来钉住「本模块不得再用全局会话」。"""

    def __call__(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("该站点必须走 short_db_session，不得回退全局 AsyncSessionLocal")


def test_loader_delegates_with_short_session_and_tenant(monkeypatch):
    fake_db = object()
    calls = []

    async def fake_load_tenant_scan_words(db, tenant_id):
        calls.append((db, tenant_id))
        return [("foo", SensitiveAction.WARN)]

    monkeypatch.setattr(loader_mod, "short_db_session", lambda: _FakeSessionCtx(fake_db))
    monkeypatch.setattr(loader_mod, "load_tenant_scan_words", fake_load_tenant_scan_words)

    tenant_uuid = uuid4()
    loader = build_scan_words_loader()
    out = asyncio.run(loader(str(tenant_uuid)))

    assert out == [("foo", SensitiveAction.WARN)]
    assert calls == [(fake_db, tenant_uuid)]


def test_build_returns_callable():
    assert callable(build_scan_words_loader())


def test_loader_never_falls_back_to_global_session(monkeypatch):
    """敏感词加载站点：全局会话换成调用即炸替身，词表仍必须从短会话读出。

    ``raising=False`` 是有意的：Task 1 之后本模块不再 import ``AsyncSessionLocal``，
    把一个「不存在的名字」换成替身，正是回退时能被抓到的原因。
    """
    fake_db = object()
    calls = []

    async def fake_load_tenant_scan_words(db, tenant_id):
        calls.append((db, tenant_id))
        return [("bar", SensitiveAction.BLOCK)]

    monkeypatch.setattr(loader_mod, "short_db_session", lambda: _FakeSessionCtx(fake_db), raising=False)
    monkeypatch.setattr(loader_mod, "AsyncSessionLocal", _Boom(), raising=False)
    monkeypatch.setattr(loader_mod, "load_tenant_scan_words", fake_load_tenant_scan_words)

    tenant_uuid = uuid4()
    out = asyncio.run(build_scan_words_loader()(str(tenant_uuid)))

    assert out == [("bar", SensitiveAction.BLOCK)]
    assert calls == [(fake_db, tenant_uuid)]
