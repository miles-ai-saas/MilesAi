"""template_loader 定向单测：短会话加载启用中 PromptTemplate content。

通过 monkeypatch short_db_session 隔离真实 db；is_marked_deleted 仅查询
``deleted_at`` 属性（缺失即视为未删），故假行无需 deleted_at 字段。
"""

import asyncio
from types import SimpleNamespace
from uuid import UUID

from miles_portal.tenant.prompts.models import PromptTemplate
from miles_portal.tenant.prompts.services import template_loader
from miles_portal.tenant.prompts.services.template_loader import build_prompt_template_loader

_TENANT_UUID = UUID("11111111-1111-1111-1111-111111111111")
_TEMPLATE_UUID = UUID("22222222-2222-2222-2222-222222222222")


class _RecordingSession:
    """假 short_db_session：__aenter__ 返回假 db，__aexit__ 收尾。"""

    def __init__(self, db, entered):
        self._db = db
        self._entered = entered

    async def __aenter__(self):
        self._entered.append(True)
        return self._db

    async def __aexit__(self, exc_type, exc, tb):
        return None


class _TrackingTemplate:
    """记录被读取字段的假 PromptTemplate。"""

    def __init__(self, *, tenant_id, content, is_active):
        self._tenant_id = tenant_id
        self._content = content
        self._is_active = is_active
        self.accessed = set()

    def __getattr__(self, name):
        raise AttributeError(name)

    @property
    def tenant_id(self):
        self.accessed.add("tenant_id")
        return self._tenant_id

    @property
    def content(self):
        self.accessed.add("content")
        return self._content

    @property
    def is_active(self):
        self.accessed.add("is_active")
        return self._is_active


class _StubDb:
    """假 AsyncSession：get 记录入参并返回预设行。"""

    def __init__(self, row):
        self.row = row
        self.get_calls = []

    async def get(self, model, pk):
        self.get_calls.append((model, pk))
        return self.row


class _Boom:
    """全局会话替身：被调用即失败，用来钉住「本模块不得再用全局会话」。"""

    def __call__(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("该站点必须走 short_db_session，不得回退全局 AsyncSessionLocal")


def test_loader_returns_active_template_content(monkeypatch):
    tpl = _TrackingTemplate(tenant_id=_TENANT_UUID, content="系统提示词", is_active=True)
    db = _StubDb(tpl)
    entered = []
    monkeypatch.setattr(template_loader, "short_db_session", lambda: _RecordingSession(db, entered))

    loader = build_prompt_template_loader()
    result = asyncio.run(loader(str(_TEMPLATE_UUID), str(_TENANT_UUID)))

    assert result == "系统提示词"
    assert db.get_calls == [(PromptTemplate, _TEMPLATE_UUID)]
    assert entered == [True]
    # 校验路径读取 tenant_id / is_active / content（is_marked_deleted 读不到 deleted_at → False）
    assert tpl.accessed == {"tenant_id", "is_active", "content"}


def test_loader_invalid_uuid_returns_none_without_db(monkeypatch):
    def _boom_factory():
        raise AssertionError("UUID 非法时不应打开 db 会话")

    monkeypatch.setattr(template_loader, "short_db_session", _boom_factory)
    loader = build_prompt_template_loader()

    assert asyncio.run(loader("not-a-uuid", "1")) is None


def test_loader_rejects_foreign_tenant_template(monkeypatch):
    foreign = SimpleNamespace(
        tenant_id=UUID("99999999-9999-9999-9999-999999999999"),
        content="其他租户模板",
        is_active=True,
    )
    db = _StubDb(foreign)
    entered = []
    monkeypatch.setattr(template_loader, "short_db_session", lambda: _RecordingSession(db, entered))

    loader = build_prompt_template_loader()
    result = asyncio.run(loader(str(_TEMPLATE_UUID), str(_TENANT_UUID)))

    assert result is None
    assert entered == [True]


def test_build_loader_returns_callable(monkeypatch):
    row = SimpleNamespace(
        tenant_id=_TENANT_UUID,
        content="工厂返回的可调用体结果",
        is_active=True,
    )
    db = _StubDb(row)
    monkeypatch.setattr(template_loader, "short_db_session", lambda: _RecordingSession(db, []))

    loader = build_prompt_template_loader()

    assert callable(loader)
    assert asyncio.run(loader(str(_TEMPLATE_UUID), str(_TENANT_UUID))) == "工厂返回的可调用体结果"


def test_loader_never_falls_back_to_global_session(monkeypatch):
    """模板加载站点：全局会话换成调用即炸替身，live 引用仍必须加载成功。

    ``raising=False`` 是有意的：Task 1 之后本模块不再 import ``AsyncSessionLocal``，
    把一个「不存在的名字」换成替身，正是回退时能被抓到的原因。
    """
    tpl = _TrackingTemplate(tenant_id=_TENANT_UUID, content="护栏内容", is_active=True)
    db = _StubDb(tpl)
    entered = []
    monkeypatch.setattr(template_loader, "short_db_session", lambda: _RecordingSession(db, entered), raising=False)
    monkeypatch.setattr(template_loader, "AsyncSessionLocal", _Boom(), raising=False)

    loader = build_prompt_template_loader()
    result = asyncio.run(loader(str(_TEMPLATE_UUID), str(_TENANT_UUID)))

    assert result == "护栏内容"
    assert db.get_calls == [(PromptTemplate, _TEMPLATE_UUID)]
    assert entered == [True]
