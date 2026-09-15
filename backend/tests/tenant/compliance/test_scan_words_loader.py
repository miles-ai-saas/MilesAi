"""scan_words_loader 定向单测：短会话委托与 tenant 解析。

monkeypatch 均打到 ``scan_words_loader`` 模块命名空间（from-import 绑定），
AsyncSessionLocal 用假 async 上下文管理器替换，不落真实 DB。
"""

import asyncio
from uuid import uuid4

from miles_core.models.compliance.constants import SensitiveAction
from miles_portal.tenant.compliance.services import scan_words_loader as loader_mod
from miles_portal.tenant.compliance.services.scan_words_loader import build_scan_words_loader


class _FakeSessionCtx:
    """假 AsyncSessionLocal：__aenter__ 返回假 db，__aexit__ 返回 None。"""

    def __init__(self, db):
        self._db = db

    async def __aenter__(self):
        return self._db

    async def __aexit__(self, exc_type, exc, tb):
        return None


def test_loader_delegates_with_own_session_and_tenant(monkeypatch):
    fake_db = object()
    calls = []

    async def fake_load_tenant_scan_words(db, tenant_id):
        calls.append((db, tenant_id))
        return [("foo", SensitiveAction.WARN)]

    monkeypatch.setattr(loader_mod, "AsyncSessionLocal", lambda: _FakeSessionCtx(fake_db))
    monkeypatch.setattr(loader_mod, "load_tenant_scan_words", fake_load_tenant_scan_words)

    tenant_uuid = uuid4()
    loader = build_scan_words_loader()
    out = asyncio.run(loader(str(tenant_uuid)))

    assert out == [("foo", SensitiveAction.WARN)]
    assert calls == [(fake_db, tenant_uuid)]


def test_build_returns_callable():
    assert callable(build_scan_words_loader())


def test_loader_reads_words_from_its_own_session(monkeypatch):
    """敏感词加载站点：词表从自开的一次会话读出，query 与既有断言不变。"""
    fake_db = object()
    calls = []

    async def fake_load_tenant_scan_words(db, tenant_id):
        calls.append((db, tenant_id))
        return [("bar", SensitiveAction.BLOCK)]

    monkeypatch.setattr(loader_mod, "AsyncSessionLocal", lambda: _FakeSessionCtx(fake_db))
    monkeypatch.setattr(loader_mod, "load_tenant_scan_words", fake_load_tenant_scan_words)

    tenant_uuid = uuid4()
    out = asyncio.run(build_scan_words_loader()(str(tenant_uuid)))

    assert out == [("bar", SensitiveAction.BLOCK)]
    assert calls == [(fake_db, tenant_uuid)]
