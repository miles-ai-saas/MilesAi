"""progress 护栏：生成任务进度读写都在自开的一次会话内完成。

``miles_ai.integrations.generative.jobs.progress`` 在 Celery 生成任务（``asyncio.run``，
每次新事件循环）内可达：``job_execution.run_generative_{video,image}_job_async`` 与
``GenerativeJobService`` 都经它读写任务进度/取消状态。engine 按事件循环持有
（见 ``infra/db/async_session``），故任务内与请求内走同一条取会话路径。

本文件把模块命名空间里的会话工厂换成假替身，断言每次读写都发生在那次自开会话里。
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from miles_ai.integrations.generative.jobs import progress as progress_mod
from miles_ai.integrations.generative.jobs.errors import GenerativeJobCancelled
from miles_ai.integrations.generative.jobs.progress import (
    GenerativeJobProgress,
    assert_generative_job_active,
    is_generative_job_cancelled,
    update_generative_job_progress,
)
from miles_core.models.model.generative_job import GenerativeJob, GenerativeJobStatus


class _StubDb:
    """假 AsyncSession：``get`` 记录入参并返回预设 job，``commit`` 计数。"""

    def __init__(self, job: object) -> None:
        self.job = job
        self.get_calls: list[tuple[object, object]] = []
        self.commit_calls = 0

    async def get(self, model: object, pk: object) -> object:
        self.get_calls.append((model, pk))
        return self.job

    async def commit(self) -> None:
        self.commit_calls += 1


class _RecordingShortSession:
    """假 AsyncSessionLocal：交出可辨识的 db，并记录开合次数。"""

    def __init__(self, db: _StubDb) -> None:
        self.db = db
        self.entered = 0
        self.exited = 0

    async def __aenter__(self) -> _StubDb:
        self.entered += 1
        return self.db

    async def __aexit__(self, *exc: object) -> bool:
        self.exited += 1
        return False


def _job(status: GenerativeJobStatus, **overrides: object) -> SimpleNamespace:
    """最小 job 替身；只带被测代码实际访问的字段。"""
    base: dict[str, object] = dict(
        id=uuid4(),
        tenant_id=uuid4(),
        status=status,
        progress_percent=None,
        progress_message=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture
def guard(monkeypatch):
    """装好护栏：自开会话替身 + 可观察的 Redis 广播替身。

    ``guard.build(job)`` 返回本次装配的观测记录（假 db / 会话替身 / 广播实参）。
    """

    def build(job: object) -> SimpleNamespace:
        db = _StubDb(job)
        short = _RecordingShortSession(db)
        publishes: list[SimpleNamespace] = []

        async def _publish(tenant_id, job_id, *, status, percent=None, message=None):  # noqa: ANN001
            publishes.append(
                SimpleNamespace(
                    tenant_id=tenant_id,
                    job_id=job_id,
                    status=status,
                    percent=percent,
                    message=message,
                )
            )

        monkeypatch.setattr(progress_mod, "AsyncSessionLocal", lambda: short)
        monkeypatch.setattr(progress_mod, "publish_generative_job_update", _publish, raising=False)
        return SimpleNamespace(db=db, short=short, publishes=publishes)

    guard.build = build
    return guard


async def test_update_progress_writes_and_publishes_on_its_own_session(guard):  # noqa: ANN001
    """进度写入：percent 夹取、message 截断、落库提交，且广播携带刚写入的值。"""
    job = _job(GenerativeJobStatus.RUNNING)
    state = guard.build(job)

    await update_generative_job_progress(job.id, percent=150, message="积" * 300)

    # 业务结果：行按夹取后的值更新并提交
    assert job.progress_percent == 100
    assert job.progress_message == "积" * 256
    assert state.db.get_calls == [(GenerativeJob, job.id)]
    assert state.db.commit_calls == 1
    # 广播必须携带刚写入 job 的值（这正是 SSE 即时感知的依据）
    assert len(state.publishes) == 1
    publish = state.publishes[0]
    assert (publish.tenant_id, publish.job_id) == (job.tenant_id, job.id)
    assert (publish.status, publish.percent, publish.message) == ("running", 100, "积" * 256)
    # 且整段读写确实落在自开的那次会话里
    assert (state.short.entered, state.short.exited) == (1, 1)


@pytest.mark.parametrize(("raw", "expected"), [(150, 100), (-5, 0), (42, 42), (0, 0)])
async def test_update_progress_clamps_percent_within_short_session(guard, raw, expected):  # noqa: ANN001
    job = _job(GenerativeJobStatus.RUNNING)
    state = guard.build(job)

    await update_generative_job_progress(job.id, percent=raw)

    assert job.progress_percent == expected
    assert state.publishes[0].percent == expected
    assert (state.short.entered, state.short.exited) == (1, 1)


async def test_update_progress_missing_job_writes_nothing_and_publishes_nothing(guard):  # noqa: ANN001
    """任务不存在：早退，不提交、不广播（仍必须是在自开会话里查的）。"""
    state = guard.build(None)

    await update_generative_job_progress(uuid4(), percent=50, message="x")

    assert state.db.commit_calls == 0
    assert state.publishes == []
    assert (state.short.entered, state.short.exited) == (1, 1)


async def test_is_cancelled_reads_on_its_own_session(guard):  # noqa: ANN001
    """取消检测：只有 CANCELLED 为真，任务不存在视为未取消——每次查询各开一次会话。"""
    cancelled = _job(GenerativeJobStatus.CANCELLED)
    state = guard.build(cancelled)
    assert await is_generative_job_cancelled(cancelled.id) is True
    assert state.db.get_calls == [(GenerativeJob, cancelled.id)]
    assert (state.short.entered, state.short.exited) == (1, 1)

    running = _job(GenerativeJobStatus.RUNNING)
    running_state = guard.build(running)
    assert await is_generative_job_cancelled(running.id) is False
    assert (running_state.short.entered, running_state.short.exited) == (1, 1)

    missing_state = guard.build(None)
    assert await is_generative_job_cancelled(uuid4()) is False
    assert (missing_state.short.entered, missing_state.short.exited) == (1, 1)


async def test_assert_active_raises_only_for_cancelled_within_short_session(guard):  # noqa: ANN001
    """轮询中断入口：已取消抛 ``GenerativeJobCancelled``，进行中放行。"""
    cancelled = _job(GenerativeJobStatus.CANCELLED)
    state = guard.build(cancelled)
    with pytest.raises(GenerativeJobCancelled):
        await assert_generative_job_active(cancelled.id)
    assert (state.short.entered, state.short.exited) == (1, 1)

    running = _job(GenerativeJobStatus.RUNNING)
    running_state = guard.build(running)
    await assert_generative_job_active(running.id)
    assert (running_state.short.entered, running_state.short.exited) == (1, 1)


async def test_progress_facade_update_writes_then_publishes_via_short_session(guard):  # noqa: ANN001
    """``GenerativeJobProgress.update`` 的真实业务结果：先查取消再写进度并广播。"""
    job = _job(GenerativeJobStatus.RUNNING)
    state = guard.build(job)

    await GenerativeJobProgress(job.id).update(30, "生成中")

    assert (job.progress_percent, job.progress_message) == (30, "生成中")
    assert state.db.commit_calls == 1
    assert [(p.status, p.percent, p.message) for p in state.publishes] == [("running", 30, "生成中")]
    # 两次自开会话：一次取消检测、一次进度写入
    assert (state.short.entered, state.short.exited) == (2, 2)
    assert state.db.get_calls == [(GenerativeJob, job.id), (GenerativeJob, job.id)]
