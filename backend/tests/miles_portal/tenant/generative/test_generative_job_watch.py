"""``watch_generative_job`` 单元测试：注入式接口（不碰真 Redis / 不碰真 DB）。

与 ``test_job_stream_events.py`` 的分工：那边用**真实调用方**（``GenerativeJobService``）
做特征化回归，这边直接测注入点，覆盖平台侧用不到的两个旋钮（``poll_interval`` /
``emit_ticks``）与首个产出契约。
"""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from uuid import uuid4

import pytest

from miles_common.redis_keys import RedisKeys
from miles_portal.tenant.generative.services.job_watch import watch_generative_job

JOB_ID = uuid4()
TENANT_ID = uuid4()
_TERMINAL = frozenset({"success", "failed", "cancelled"})


def _job(status: str, **overrides):  # noqa: ANN202
    base = dict(id=JOB_ID, tenant_id=TENANT_ID, status=status, progress_message=None, progress_percent=None, result=None)
    base.update(overrides)
    return SimpleNamespace(**base)


class _PollOverflow(BaseException):
    """轮询次数超限的守卫异常。

    必须继承 ``BaseException`` 而非 ``AssertionError``：``watch_generative_job`` 的宽
    ``except Exception`` 是有意的 Redis 降级路径，``AssertionError``（``Exception`` 子类）
    会被它吞掉并转入 DB 回退 —— 守卫实际变成「把 bug 变成降级路径」，用例仍会假通过
    （例如 Pub/Sub 循环无界时，兜底终查兜住了本应失败的断言）。
    """


class _FakePubSub:
    """假 pubsub：每次 poll 把时钟推进 ``timeout`` 秒，等价于「一次阻塞轮询 = 那么长时间」。"""

    def __init__(self, messages, *, clock, max_polls=500):  # noqa: ANN001
        self._messages = list(messages)
        self._clock = clock
        self._max_polls = max_polls
        self.polls = 0
        self.timeouts: list[float | None] = []
        self.calls: list[tuple[str, str]] = []

    async def subscribe(self, channel) -> None:  # noqa: ANN001
        self.calls.append(("subscribe", channel))

    async def get_message(self, timeout=None):  # noqa: ANN001
        self.timeouts.append(timeout)
        self.polls += 1
        if self.polls > self._max_polls:
            raise _PollOverflow(f"轮询次数超限（>{self._max_polls}）：循环未受上限约束")
        self._clock["t"] += timeout or 0.0
        return self._messages.pop(0) if self._messages else None

    async def unsubscribe(self, channel) -> None:  # noqa: ANN001
        self.calls.append(("unsubscribe", channel))


@pytest.fixture
def env(monkeypatch):  # noqa: ANN001
    """装配：可控时钟、可编排 reload、假 redis、可记录的 sleep。"""

    def build(jobs, *, redis="ok", messages=(), unsubscribe_error=None):  # noqa: ANN001
        state = SimpleNamespace(
            jobs=list(jobs),
            clock={"t": 0.0},
            reloads=0,
            sleeps=[],
        )

        async def _reload():  # noqa: ANN202
            state.reloads += 1
            if len(state.jobs) > 1:
                return state.jobs.pop(0)
            return state.jobs[0]

        pubsub = _FakePubSub(messages, clock=state.clock)
        if unsubscribe_error is not None:

            async def _failing_unsubscribe(channel):  # noqa: ANN001
                raise unsubscribe_error

            pubsub.unsubscribe = _failing_unsubscribe

        async def _sleep(seconds):  # noqa: ANN001
            state.sleeps.append(seconds)
            # 与 ``_FakePubSub.get_message`` 同理的守卫：降级路径若被改成无界，用例会在
            # 这里**失败**，而不是把测试机挂住（``asyncio.sleep`` 被换成了直通，墙钟不推进）。
            if len(state.sleeps) > 1000:
                raise _PollOverflow("降级轮询次数超限（>1000）：回退循环未受上限约束")

        def _get_redis():  # noqa: ANN202
            if redis == "raise":
                raise RuntimeError("redis 不可用")
            return SimpleNamespace(pubsub=lambda: pubsub)

        monkeypatch.setattr("miles_core.infra.redis.get_redis", _get_redis)
        # 时钟只由假 pubsub 的轮询推进：上限在有限次轮询后确定性到达，不依赖真实等待
        monkeypatch.setattr(time, "monotonic", lambda: state.clock["t"])
        monkeypatch.setattr(asyncio, "sleep", _sleep)
        state.pubsub = pubsub
        state.reload = _reload
        return state

    return build


async def _watch(state, **overrides):  # noqa: ANN001, ANN202
    kwargs = dict(
        job_id=JOB_ID,
        tenant_id=TENANT_ID,
        reload=state.reload,
        is_terminal=lambda job: job.status in _TERMINAL,
        max_seconds=3.0,
        poll_interval=1.0,
    )
    kwargs.update(overrides)
    return [item async for item in watch_generative_job(**kwargs)]


@pytest.mark.asyncio
async def test_first_yield_is_snapshot_and_terminal_job_skips_subscription(env, monkeypatch):  # noqa: ANN001
    state = env([_job("success")])

    items = await _watch(state)

    assert [j.status for j in items] == ["success"]
    assert state.pubsub.calls == []  # 终态任务不订阅：没有后续更新可等


@pytest.mark.asyncio
async def test_pubsub_message_yields_reloaded_snapshot(env):  # noqa: ANN001
    state = env([_job("running"), _job("success")], messages=[{"type": "message"}])

    items = await _watch(state)

    assert [j.status for j in items] == ["running", "success"]
    assert state.pubsub.calls == [
        ("subscribe", RedisKeys.generative_job_progress(str(TENANT_ID), str(JOB_ID))),
        ("unsubscribe", RedisKeys.generative_job_progress(str(TENANT_ID), str(JOB_ID))),
    ]


@pytest.mark.asyncio
async def test_idle_poll_yields_tick_only_when_enabled(env):  # noqa: ANN001
    """订阅方要靠刻度才有机会发保活帧；平台侧不打开，故不被刻度打扰。

    ``max_seconds=2.0`` / ``poll_interval=1.0``：时钟每轮加 1.0（整数累加，无浮点漂移），
    故恰好两轮空等、两个刻度。
    """
    with_ticks = await _watch(env([_job("running")]), max_seconds=2.0, emit_ticks=True)
    without_ticks = await _watch(env([_job("running")]), max_seconds=2.0)

    assert [item for item in with_ticks if item is None] == [None, None]
    assert [item for item in without_ticks if item is None] == []


@pytest.mark.asyncio
async def test_poll_timeout_is_the_injected_interval(env):  # noqa: ANN001
    state = env([_job("running")])

    await _watch(state, poll_interval=2.0)

    assert set(state.pubsub.timeouts) == {2.0}


@pytest.mark.asyncio
async def test_fallback_final_query_yields_terminal_job_not_yet_yielded(env):  # noqa: ANN001
    """兜底终查：Pub/Sub 消息丢了也不能让对端永久等待。"""
    state = env([_job("running"), _job("success")])

    items = await _watch(state)

    assert [j.status for j in items] == ["running", "success"]


@pytest.mark.asyncio
async def test_redis_unavailable_falls_back_to_db_polling_with_injected_interval(env):  # noqa: ANN001
    """降级路径的刷新间隔来自注入参数（默认值须与重构前一致：1.0 秒）。"""
    # 中间要留一个「仍非终态」的快照，否则一轮就 break、sleep 根本没机会发生
    state = env([_job("running"), _job("running"), _job("success")], redis="raise")

    items = await _watch(state)

    assert [j.status for j in items] == ["running", "running", "success"]
    assert state.sleeps == [1.0]


@pytest.mark.asyncio
async def test_db_polling_bound_scales_with_max_seconds_over_poll_interval(env):  # noqa: ANN001
    """上限 = ``max_seconds / poll_interval``：A2A 侧 1800/2.0 = 900 次，而不是写死 120。"""
    state = env([_job("running")], redis="raise")

    await _watch(state, max_seconds=6.0, poll_interval=2.0)

    assert state.sleeps == [2.0, 2.0, 2.0]
    assert state.reloads == 4  # 首帧 1 次 + 3 次轮询


@pytest.mark.asyncio
async def test_unsubscribe_failure_is_swallowed(env):  # noqa: ANN001
    state = env([_job("running"), _job("success")], unsubscribe_error=RuntimeError("连接已断"))

    items = await _watch(state)

    assert [j.status for j in items] == ["running", "success"]
