"""``short_db_session`` 的上下文选择：Worker 绑定了 maker 就必须走它。

Celery 任务每次 ``asyncio.run`` 都是新 loop，全局 engine 池里属于上一个 loop 的连接
复用即抛 ``got Future attached to a different loop``。``short_db_session`` 存在的全部
意义就是「有 worker maker 时绝不碰全局 ``AsyncSessionLocal``」；本文件把这个选择
锁成不变量：把全局换成「调用即炸」的替身，一旦回退就会带着明确信息失败。

两个方向都要锁：绑定时**必须**用 worker maker（不能回退全局），未绑定时**才**回退
全局（API / 脚本路径靠它工作，若退化成「永远 worker」同样是 bug）。
"""

import pytest

from miles_core.infra.db import async_session as async_session_mod
from miles_core.infra.db.async_session import (
    _reset_worker_sessionmaker,
    _set_worker_sessionmaker,
    short_db_session,
)


class _Session:
    """记录 enter/exit 次数的最小会话替身。"""

    def __init__(self) -> None:
        self.entered = 0
        self.exited = 0

    async def __aenter__(self) -> "_Session":
        self.entered += 1
        return self

    async def __aexit__(self, *exc: object) -> bool:
        self.exited += 1
        return False


class _Maker:
    """worker sessionmaker 替身：记录它产出的会话。"""

    def __init__(self) -> None:
        self.sessions: list[_Session] = []

    def __call__(self) -> _Session:
        session = _Session()
        self.sessions.append(session)
        return session


def _boom(*args: object, **kwargs: object) -> None:
    """全局 ``AsyncSessionLocal`` 替身：被调用即炸。"""
    raise AssertionError("worker 上下文里回退了全局 AsyncSessionLocal（跨 loop 复用连接必失败）")


@pytest.mark.asyncio
async def test_worker_maker_wins_and_global_is_never_touched(monkeypatch):
    """绑定 worker maker 时：会话来自该 maker，全局一次都没被碰。"""
    maker = _Maker()
    # raising=False：即便被测模块某天改名/去掉全局工厂，本用例也要能完成替换并断言。
    monkeypatch.setattr(async_session_mod, "AsyncSessionLocal", _boom, raising=False)

    token = _set_worker_sessionmaker(maker)
    try:
        async with short_db_session() as db:
            assert isinstance(db, _Session)
    finally:
        _reset_worker_sessionmaker(token)

    assert len(maker.sessions) == 1
    assert maker.sessions[0].entered == 1
    assert maker.sessions[0].exited == 1


@pytest.mark.asyncio
async def test_without_worker_maker_falls_back_to_global(monkeypatch):
    """未绑定 worker maker 时回退全局——这是 API / 脚本的预期路径，不是回退 bug。"""
    short = _Session()
    calls: list[int] = []

    def _fake_global() -> _Session:
        calls.append(1)
        return short

    monkeypatch.setattr(async_session_mod, "AsyncSessionLocal", _fake_global, raising=False)

    token = _set_worker_sessionmaker(None)
    try:
        async with short_db_session() as db:
            assert db is short
    finally:
        _reset_worker_sessionmaker(token)

    assert calls == [1]
    assert short.entered == 1
    assert short.exited == 1
