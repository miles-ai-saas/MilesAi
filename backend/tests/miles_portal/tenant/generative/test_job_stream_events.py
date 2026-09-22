"""``GenerativeJobService.stream_job_events`` SSE 帧特征化测试（重构前锁定行为）。

该函数有 4 处「``expire_all`` → 取 job → 序列化 → yield 一帧」的重复序列：
初次推送、Pub/Sub 循环内、Pub/Sub 兜底终查、Redis 不可用的 DB 轮询。
本文件逐条覆盖这 4 条路径，使后续提取公共序列时可回归验证。

时钟说明
--------
生产代码 ``get_message(timeout=1.0)`` 会**阻塞至多 1 秒、超时后返回 ``None``**
（redis-py 的 ``Connection.read_response`` 在显式给定 timeout 时返回 ``None``
而非抛错），因此该循环每秒轮询一次、**不会空转**，轮询次数被 ``< 120`` 上限
约束为 120 次。

本文件的假 pubsub 立即返回，故让**每轮 poll 把时钟推进 1.0s**，等价于「一次
poll 对应一秒真实时间」，使上限在 120 次轮询后确定性到达，测试无需真实等待。
另把 ``asyncio.sleep`` 置为直通，避免 DB 轮询回退路径真等到 2 分钟。
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from miles_common.redis_keys import RedisKeys
from miles_core.models.model.generative_job import GenerativeJobStatus
from miles_core.tenant import TenantContext
from miles_portal.tenant.generative.services import job as job_module

# 一次 poll 推进 1.0s：与生产 get_message(timeout=1.0) 的阻塞时长一一对应。
_POLL_SECONDS = 1.0


def _sse_job(status: GenerativeJobStatus, **overrides) -> SimpleNamespace:
    now = datetime.now(UTC)
    base = dict(
        id=uuid4(),
        tenant_id=uuid4(),
        kind="video",
        status=status,
        source="api",
        progress_message=None,
        progress_percent=None,
        params={},
        result=None,
        error_message=None,
        celery_task_id=None,
        celery_task_record_id=None,
        created_at=now,
        updated_at=now,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _status_of(frame: str) -> str:
    return json.loads(frame.removeprefix("data: ").strip())["status"]


def _tenant_ctx(tenant_id=None):  # noqa: ANN001
    return TenantContext(
        user_id=uuid4(),
        tenant_id=tenant_id or uuid4(),
        username="t",
        is_superuser=False,
        permissions=frozenset(),
    )


async def _collect(agen) -> list[str]:  # noqa: ANN001
    return [frame async for frame in agen]


class _FakePubSub:
    """假 pubsub：每次 poll 把时钟推进 1.0s，对应生产端阻塞 1 秒。

    ``get_message`` 记录收到的 ``timeout`` 供测试断言——这是本循环不空转的唯一
    依据。此处不在方法内断言：异常会被 ``stream_job_events`` 的宽 except 吞掉并
    回退 DB 轮询，反而掩盖问题；改为收集后由独立用例断言，失败才清晰。
    """

    def __init__(self, messages, calls, clock, *, max_polls=200):  # noqa: ANN001
        self._messages = list(messages)
        self._calls = calls
        self._clock = clock
        self._max_polls = max_polls
        self.polls = 0
        self.timeouts = []

    async def subscribe(self, channel) -> None:  # noqa: ANN001
        self._calls.append(("subscribe", channel))

    async def get_message(self, timeout=None):  # noqa: ANN001
        self.timeouts.append(timeout)
        self.polls += 1
        if self.polls > self._max_polls:
            raise AssertionError(f"轮询次数超限（>{self._max_polls}）：循环未受上限约束")
        self._clock["t"] += _POLL_SECONDS
        return self._messages.pop(0) if self._messages else None

    async def unsubscribe(self, channel) -> None:  # noqa: ANN001
        self._calls.append(("unsubscribe", channel))


class _FakeRedis:
    def __init__(self, pubsub):  # noqa: ANN001
        self._pubsub = pubsub

    def pubsub(self):  # noqa: ANN001
        return self._pubsub


@pytest.fixture
def harness(monkeypatch):
    """装配 SSE 场景：可编排的 job 序列 + 可编排的 Redis + 可控时钟。"""

    def build(jobs, *, redis="ok", pubsub_messages=(), unsubscribe_error=None):
        state = SimpleNamespace(
            timeline=[],
            pubsub_calls=[],
            jobs=list(jobs),
            clock={"t": 0.0},
        )

        async def _get(db, ctx, job_id):  # noqa: ANN001
            state.timeline.append("get")
            if len(state.jobs) > 1:
                return state.jobs.pop(0)
            return state.jobs[0]

        state.db = SimpleNamespace(expire_all=lambda: state.timeline.append("expire"))

        pubsub = _FakePubSub(pubsub_messages, state.pubsub_calls, state.clock)
        if unsubscribe_error is not None:

            async def _failing_unsubscribe(channel):  # noqa: ANN001
                raise unsubscribe_error

            pubsub.unsubscribe = _failing_unsubscribe

        async def _no_sleep(_seconds):  # noqa: ANN001
            """DB 轮询回退路径的 ``asyncio.sleep(1)`` 直接跳过。

            该路径在 Redis 不可用或轮询异常时触发，若真等 1s×120 会让用例挂 2 分钟。
            """

        def _get_redis():
            if redis == "raise":
                raise RuntimeError("redis 不可用")
            return _FakeRedis(pubsub)

        monkeypatch.setattr(job_module, "get_generative_job_for_tenant", _get)
        monkeypatch.setattr("miles_core.infra.redis.get_redis", _get_redis)
        # 时钟只由假 pubsub 的每次轮询推进：使 ``< 120`` 上限在 120 次轮询后
        # 确定性到达，不依赖真实等待。
        monkeypatch.setattr(time, "monotonic", lambda: state.clock["t"])
        monkeypatch.setattr(asyncio, "sleep", _no_sleep)
        state.pubsub = pubsub
        return state

    harness.build = build
    return harness


async def _stream(state, ctx, job_id) -> list[str]:  # noqa: ANN001
    service = job_module.GenerativeJobService(state.db, ctx)
    return await _collect(service.stream_job_events(job_id))


# --------------------------------------------------------------------------- #
# 路径 1：初次推送
# --------------------------------------------------------------------------- #


async def test_terminal_job_yields_single_frame_then_stops(harness):  # noqa: ANN001
    job = _sse_job(GenerativeJobStatus.SUCCESS)
    state = harness.build([job])

    frames = await _stream(state, _tenant_ctx(job.tenant_id), job.id)

    assert len(frames) == 1
    assert frames[0].startswith("data: ")
    assert frames[0].endswith("\n\n")
    assert _status_of(frames[0]) == "success"


async def test_frame_keeps_chinese_unescaped(harness):  # noqa: ANN001
    job = _sse_job(GenerativeJobStatus.SUCCESS, progress_message="已完成")
    state = harness.build([job])

    frames = await _stream(state, _tenant_ctx(job.tenant_id), job.id)

    assert "已完成" in frames[0]
    assert "\\u" not in frames[0]


async def test_initial_frame_precedes_with_expire_all(harness):  # noqa: ANN001
    job = _sse_job(GenerativeJobStatus.SUCCESS)
    state = harness.build([job])

    await _stream(state, _tenant_ctx(job.tenant_id), job.id)

    assert state.timeline == ["expire", "get"]


# --------------------------------------------------------------------------- #
# 路径 2：Pub/Sub 收到消息
# --------------------------------------------------------------------------- #


async def test_pubsub_message_yields_second_frame_with_new_status(harness):  # noqa: ANN001
    running = _sse_job(GenerativeJobStatus.RUNNING)
    done = _sse_job(GenerativeJobStatus.SUCCESS, id=running.id, tenant_id=running.tenant_id)
    state = harness.build([running, done], pubsub_messages=[{"type": "message", "data": b"x"}])

    frames = await _stream(state, _tenant_ctx(running.tenant_id), running.id)

    assert [_status_of(f) for f in frames] == ["running", "success"]
    assert state.timeline == ["expire", "get", "expire", "get"]


async def test_non_message_payload_is_ignored_without_db_hit(harness):  # noqa: ANN001
    running = _sse_job(GenerativeJobStatus.RUNNING)
    done = _sse_job(GenerativeJobStatus.SUCCESS, id=running.id, tenant_id=running.tenant_id)
    state = harness.build([running, done], pubsub_messages=[{"type": "subscribe"}])

    frames = await _stream(state, _tenant_ctx(running.tenant_id), running.id)

    # 中间那次非 message 通知不取库：只有「初次 + 兜底终查」两次取库
    assert [_status_of(f) for f in frames] == ["running", "success"]
    assert state.timeline == ["expire", "get", "expire", "get"]


async def test_pubsub_subscribes_then_unsubscribes_tenant_channel(harness):  # noqa: ANN001
    running = _sse_job(GenerativeJobStatus.RUNNING)
    done = _sse_job(GenerativeJobStatus.SUCCESS, id=running.id, tenant_id=running.tenant_id)
    state = harness.build([running, done])

    await _stream(state, _tenant_ctx(running.tenant_id), running.id)

    expected = RedisKeys.generative_job_progress(str(running.tenant_id), str(running.id))
    assert state.pubsub_calls == [("subscribe", expected), ("unsubscribe", expected)]


# --------------------------------------------------------------------------- #
# 路径 3：Pub/Sub 无终态消息时的兜底终查
# --------------------------------------------------------------------------- #


async def test_fallback_final_query_after_pubsub_timeout(harness):  # noqa: ANN001
    running = _sse_job(GenerativeJobStatus.RUNNING)
    done = _sse_job(GenerativeJobStatus.SUCCESS, id=running.id, tenant_id=running.tenant_id)
    state = harness.build([running, done])

    frames = await _stream(state, _tenant_ctx(running.tenant_id), running.id)

    assert [_status_of(f) for f in frames] == ["running", "success"]
    assert state.timeline == ["expire", "get", "expire", "get"]


async def test_fallback_final_query_does_not_yield_for_non_terminal_job(harness):  # noqa: ANN001
    running = _sse_job(GenerativeJobStatus.RUNNING)
    state = harness.build([running])

    frames = await _stream(state, _tenant_ctx(running.tenant_id), running.id)

    assert [_status_of(f) for f in frames] == ["running"]


async def test_poll_loop_is_bounded_to_120_seconds(harness):  # noqa: ANN001
    """每次阻塞轮询 1s，``< 120`` 上限即 120 次：SSE 不会无限占用连接。"""
    running = _sse_job(GenerativeJobStatus.RUNNING)
    state = harness.build([running])

    await _stream(state, _tenant_ctx(running.tenant_id), running.id)

    assert state.pubsub.polls == 120


async def test_every_poll_passes_a_blocking_timeout(harness):  # noqa: ANN001
    """守住「不空转」的唯一依据：每次 get_message 都必须传非 0 timeout。

    省略 timeout 时 redis-py 默认 0.0 为非阻塞，循环会立刻空转打满 CPU。
    """
    running = _sse_job(GenerativeJobStatus.RUNNING)
    done = _sse_job(GenerativeJobStatus.SUCCESS, id=running.id, tenant_id=running.tenant_id)
    state = harness.build([running, done], pubsub_messages=[{"type": "message"}])

    await _stream(state, _tenant_ctx(running.tenant_id), running.id)

    assert state.pubsub.timeouts
    assert all(t for t in state.pubsub.timeouts), f"存在非阻塞轮询: {state.pubsub.timeouts}"


# --------------------------------------------------------------------------- #
# 路径 4：Redis 不可用 → DB 轮询
# --------------------------------------------------------------------------- #


async def test_redis_unavailable_falls_back_to_db_polling(harness):  # noqa: ANN001
    running = _sse_job(GenerativeJobStatus.RUNNING)
    done = _sse_job(GenerativeJobStatus.SUCCESS, id=running.id, tenant_id=running.tenant_id)
    state = harness.build([running, done], redis="raise")

    frames = await _stream(state, _tenant_ctx(running.tenant_id), running.id)

    assert [_status_of(f) for f in frames] == ["running", "success"]
    assert state.timeline == ["expire", "get", "expire", "get"]


async def test_db_polling_emits_one_frame_per_reload(harness):  # noqa: ANN001
    pending = _sse_job(GenerativeJobStatus.PENDING)
    running = _sse_job(GenerativeJobStatus.RUNNING, id=pending.id, tenant_id=pending.tenant_id)
    done = _sse_job(GenerativeJobStatus.SUCCESS, id=pending.id, tenant_id=pending.tenant_id)
    state = harness.build([pending, running, running, done], redis="raise")

    frames = await _stream(state, _tenant_ctx(pending.tenant_id), pending.id)

    assert [_status_of(f) for f in frames] == ["pending", "running", "running", "success"]


# --------------------------------------------------------------------------- #
# 收尾
# --------------------------------------------------------------------------- #


async def test_unsubscribe_failure_is_swallowed(harness):  # noqa: ANN001
    running = _sse_job(GenerativeJobStatus.RUNNING)
    done = _sse_job(GenerativeJobStatus.SUCCESS, id=running.id, tenant_id=running.tenant_id)
    state = harness.build([running, done], unsubscribe_error=RuntimeError("连接已断"))

    frames = await _stream(state, _tenant_ctx(running.tenant_id), running.id)

    assert [_status_of(f) for f in frames] == ["running", "success"]
