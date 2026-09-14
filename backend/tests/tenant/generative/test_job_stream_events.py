"""``GenerativeJobService.stream_job_events`` SSE 帧特征化测试（重构前锁定行为）。

该函数有 4 处「``expire_all`` → 取 job → 序列化 → yield 一帧」的重复序列：
初次推送、Pub/Sub 循环内、Pub/Sub 兜底终查、Redis 不可用的 DB 轮询。
本文件逐条覆盖这 4 条路径，使后续提取公共序列时可回归验证。

时钟说明
--------
Pub/Sub 循环 ``while time.monotonic() - start < 120`` 内**没有 sleep**：若客户端
立刻返回空，会忙等到 120s。为让测试确定性退出，本文件的假 pubsub 每次 poll 后
把时钟推到 1000s（``clock="frozen"``）；需要走 ``asyncio.sleep`` 的 DB 轮询用例
则用 ``clock="advance"``，让每次取时钟都前进，使 sleep 立即返回。
"""

from __future__ import annotations

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

_CLOCK_JUMP = 1000.0


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
    """假 pubsub：每次 poll 后推快时钟，并在空转超限时直接失败（而非挂死 120s）。"""

    def __init__(self, messages, calls, clock, *, max_empty_polls=20):  # noqa: ANN001
        self._messages = list(messages)
        self._calls = calls
        self._clock = clock
        self._max_empty_polls = max_empty_polls
        self._empty_polls = 0

    async def subscribe(self, channel) -> None:  # noqa: ANN001
        self._calls.append(("subscribe", channel))

    async def get_message(self, timeout=None):  # noqa: ANN001
        self._clock["jump"] = _CLOCK_JUMP
        if self._messages:
            return self._messages.pop(0)
        self._empty_polls += 1
        if self._empty_polls > self._max_empty_polls:
            raise AssertionError("Pub/Sub 空转超限：循环内无 sleep，测试未推快时钟")
        return None

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

    def build(jobs, *, redis="ok", pubsub_messages=(), unsubscribe_error=None, clock="frozen"):
        state = SimpleNamespace(
            timeline=[],
            pubsub_calls=[],
            jobs=list(jobs),
            clock={"base": 0.0, "jump": 0.0, "ticks": 0},
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

        def _mono() -> float:
            if clock == "advance":
                state.clock["ticks"] += 1
                return state.clock["base"] + 200.0 * state.clock["ticks"]
            return state.clock["base"] + state.clock["jump"]

        def _get_redis():
            if redis == "raise":
                raise RuntimeError("redis 不可用")
            return _FakeRedis(pubsub)

        monkeypatch.setattr(job_module, "get_generative_job_for_tenant", _get)
        monkeypatch.setattr("miles_core.infra.redis.get_redis", _get_redis)
        monkeypatch.setattr(time, "monotonic", _mono)
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


# --------------------------------------------------------------------------- #
# 路径 4：Redis 不可用 → DB 轮询
# --------------------------------------------------------------------------- #


async def test_redis_unavailable_falls_back_to_db_polling(harness):  # noqa: ANN001
    running = _sse_job(GenerativeJobStatus.RUNNING)
    done = _sse_job(GenerativeJobStatus.SUCCESS, id=running.id, tenant_id=running.tenant_id)
    state = harness.build([running, done], redis="raise", clock="advance")

    frames = await _stream(state, _tenant_ctx(running.tenant_id), running.id)

    assert [_status_of(f) for f in frames] == ["running", "success"]
    assert state.timeline == ["expire", "get", "expire", "get"]


async def test_db_polling_emits_one_frame_per_reload(harness):  # noqa: ANN001
    pending = _sse_job(GenerativeJobStatus.PENDING)
    running = _sse_job(GenerativeJobStatus.RUNNING, id=pending.id, tenant_id=pending.tenant_id)
    done = _sse_job(GenerativeJobStatus.SUCCESS, id=pending.id, tenant_id=pending.tenant_id)
    state = harness.build([pending, running, running, done], redis="raise", clock="advance")

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
