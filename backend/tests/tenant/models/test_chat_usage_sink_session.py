"""ChatUsageSink 不得借用调用方会话。

生成阶段要释放请求会话连接，前提是用量写入不再挂在调用方事务上。这里锁定两点：
构造签名不含 db；record 自开短会话并提交，且完全不触碰调用方会话。
"""

import inspect
from uuid import uuid4

import pytest

from miles_core.models.model import ModelConfig, ModelUsageLog
from miles_portal.tenant.models.services import usage as usage_mod
from miles_portal.tenant.models.services.usage import ChatUsageSink


def _model() -> ModelConfig:
    return ModelConfig(id=uuid4(), name="m", provider="openai", model_name="x")


class _ShortSession:
    """替身：记录 add 的行，并记录是否 commit。"""

    def __init__(self) -> None:
        self.rows: list[object] = []
        self.commits = 0

    def add(self, row: object) -> None:
        self.rows.append(row)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1


def test_chat_usage_sink_has_no_db_parameter():
    """结构不变量：不接收调用方会话，就不可能在生成期间抓住它。"""
    assert "db" not in inspect.signature(ChatUsageSink.__init__).parameters


@pytest.mark.asyncio
async def test_record_uses_its_own_session_and_commits(monkeypatch):
    short = _ShortSession()
    monkeypatch.setattr(usage_mod, "AsyncSessionLocal", lambda: _cm(short))

    class _Caller:
        """调用方会话替身：被碰一下就记账。"""

        def __init__(self) -> None:
            self.touched = 0

        def add(self, row: object) -> None:
            self.touched += 1

        async def flush(self) -> None:
            self.touched += 1

    caller = _Caller()
    model = _model()
    source_id = uuid4()

    sink = ChatUsageSink(tenant_id=uuid4(), model=model, source_id=source_id)
    await sink.record(prompt_tokens=100, completion_tokens=20)

    assert len(short.rows) == 1
    row = short.rows[0]
    assert isinstance(row, ModelUsageLog)
    assert row.model_config_id == model.id
    assert row.source == "chat"
    assert row.source_id == source_id
    assert short.commits == 1
    assert caller.touched == 0, "不得触碰调用方会话"


class _cm:
    """最小 async context manager（AsyncSessionLocal 的替身）。"""

    def __init__(self, session: object) -> None:
        self._session = session

    async def __aenter__(self) -> object:
        return self._session

    async def __aexit__(self, *exc: object) -> bool:
        return False
