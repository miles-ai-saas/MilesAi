"""内置 compliance_check_text：租户敏感词自检（只读、不写拦截审计）。"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from miles_common.exceptions import BadRequestError
from miles_core.models.compliance.constants import SensitiveAction
from miles_portal.tenant.tools.builtins import handlers as handlers_mod


def _ctx() -> SimpleNamespace:
    return SimpleNamespace(tenant_id=uuid4())


async def test_no_library_reports_scanning_disabled(monkeypatch):
    async def fake_words(db, tenant_id):
        return []

    monkeypatch.setattr(handlers_mod, "load_tenant_scan_words", fake_words)
    out = await handlers_mod.handle_compliance_check_text(
        {"text": "任意内容"},
        db=SimpleNamespace(),
        ctx=_ctx(),
    )
    assert out == {
        "scanning_enabled": False,
        "blocked": False,
        "warned": False,
        "worst_action": None,
        "matches": [],
        "match_count": 0,
    }


async def test_reports_hits_and_worst_action(monkeypatch):
    async def fake_words(db, tenant_id):
        return [("违规", SensitiveAction.BLOCK), ("注意", SensitiveAction.WARN)]

    monkeypatch.setattr(handlers_mod, "load_tenant_scan_words", fake_words)
    out = await handlers_mod.handle_compliance_check_text(
        {"text": "这里有违规也有注意"},
        db=SimpleNamespace(),
        ctx=_ctx(),
    )
    assert out["scanning_enabled"] is True
    assert out["blocked"] is True
    assert out["warned"] is True
    assert out["worst_action"] == "block"
    assert out["match_count"] == 2
    assert {m["word"] for m in out["matches"]} == {"违规", "注意"}


async def test_does_not_write_intercept_log(monkeypatch):
    async def fake_words(db, tenant_id):
        return [("违规", SensitiveAction.BLOCK)]

    class _Db:
        def __init__(self) -> None:
            self.added: list = []

        def add(self, row) -> None:
            self.added.append(row)

    monkeypatch.setattr(handlers_mod, "load_tenant_scan_words", fake_words)
    db = _Db()
    await handlers_mod.handle_compliance_check_text({"text": "违规"}, db=db, ctx=_ctx())
    assert db.added == []


async def test_requires_text():
    with pytest.raises(BadRequestError):
        await handlers_mod.handle_compliance_check_text({}, db=SimpleNamespace(), ctx=_ctx())
