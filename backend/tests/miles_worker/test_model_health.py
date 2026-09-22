"""model_health：厂商探测不得占用 DB 会话。"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from miles_core.models.model.catalog import ModelPublishStatus
from miles_worker.tasks import model_health


class _ScalarAll:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return self._rows


class _ExecuteResult:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def scalars(self) -> _ScalarAll:
        return _ScalarAll(self._rows)


class _TrackingSession:
    """记录会话开合；供断言 litellm 调用时无活跃会话。"""

    def __init__(
        self,
        *,
        active: list[int],
        opened: list[int],
        load_rows: list[object],
        write_row: object | None,
    ) -> None:
        self._active = active
        self._opened = opened
        self._load_rows = load_rows
        self._write_row = write_row
        self.committed = False

    async def __aenter__(self) -> _TrackingSession:
        self._opened.append(1)
        self._active[0] += 1
        return self

    async def __aexit__(self, *args: object) -> None:
        self._active[0] -= 1

    async def execute(self, _stmt: object) -> _ExecuteResult:
        return _ExecuteResult(self._load_rows)

    def expunge(self, _obj: object) -> None:
        return None

    def expunge_all(self) -> None:
        return None

    async def get(self, _model: object, _id: object) -> object | None:
        return self._write_row

    async def commit(self) -> None:
        self.committed = True


def _chat_model(**overrides: object) -> SimpleNamespace:
    base = {
        "id": uuid4(),
        "name": "probe-model",
        "tenant_id": uuid4(),
        "publish_status": ModelPublishStatus.PUBLISHED.value,
        "extra": {},
        "provider": "openai",
        "model_name": "gpt-test",
        "vendor": "openai",
        "model_type": "llm",
        "api_base": None,
        "api_key_encrypted": "sk-test",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.mark.asyncio
async def test_litellm_not_called_while_session_active(monkeypatch: pytest.MonkeyPatch) -> None:
    """探测阶段不得持有 AsyncSession：load / write 各开一次，litellm 时 active==0。"""
    active = [0]
    opened: list[int] = []
    load_model = _chat_model()
    write_model = _chat_model(id=load_model.id, extra={})
    sessions: list[_TrackingSession] = []

    def _session_factory() -> _TrackingSession:
        session = _TrackingSession(
            active=active,
            opened=opened,
            load_rows=[load_model],
            write_row=write_model,
        )
        sessions.append(session)
        return session

    active_at_litellm: list[int] = []

    async def _fake_litellm(_model: object, _messages: object, **_kwargs: object) -> str:
        active_at_litellm.append(active[0])
        return "pong"

    monkeypatch.setattr(model_health, "AsyncSessionLocal", _session_factory)
    monkeypatch.setattr(model_health, "litellm_chat_completion", _fake_litellm)

    result = await model_health._probe_models_async()

    assert result == "checked=1 ok=1"
    assert active_at_litellm == [0], "litellm 调用时不得仍持有 DB 会话"
    assert len(opened) == 2, "须拆成 load 会话与 write 会话"
    assert sessions[-1].committed is True
    assert write_model.extra["health_status"] == "ok"
