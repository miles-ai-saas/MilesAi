"""生图/生视频 Celery 任务的状态回写特征化测试（重构前锁定行为）。

除锁定「RUNNING → 终态」的调用序列与返回值映射外，本文件刻意用参数化断言：
``GenerativeJobNotFound`` 与任意 ``Exception`` 的处理**结果完全一致**——这是
后续删除该冗余 except 子句的依据。
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from miles_core.models.task.task_record import TaskStatus
from miles_integrations.generative.jobs.errors import GenerativeJobCancelled, GenerativeJobNotFound
from miles_worker.tasks import generative as worker_generative

TASKS = {
    "video": worker_generative.run_generative_video_job,
    "image": worker_generative.run_generative_image_job,
}


@pytest.fixture
def recorder(monkeypatch):
    """接管 task 状态回写与事件循环，返回可观测记录。"""
    calls = []

    def _sync(celery_task_id, status, *, fail_reason=None):
        calls.append(SimpleNamespace(celery_task_id=celery_task_id, status=status, fail_reason=fail_reason))

    def _install(raise_exc=None):
        def _run_coro(coro):
            coro.close()  # 避免 "coroutine was never awaited" 噪音
            if raise_exc is not None:
                raise raise_exc

        monkeypatch.setattr(worker_generative, "sync_task_by_celery_id", _sync)
        monkeypatch.setattr(worker_generative, "_run_coro", _run_coro)
        return calls

    recorder.install = _install
    return recorder


@pytest.mark.parametrize("kind", ["video", "image"])
def test_success_writes_running_then_success_and_returns_ok(recorder, kind):  # noqa: ANN001
    calls = recorder.install()

    result = TASKS[kind](str(uuid4()))

    assert result == "ok"
    assert [(c.status, c.fail_reason) for c in calls] == [
        (TaskStatus.RUNNING, None),
        (TaskStatus.SUCCESS, None),
    ]


@pytest.mark.parametrize("kind", ["video", "image"])
def test_cancelled_writes_cancelled_with_reason_and_returns_cancelled(recorder, kind):  # noqa: ANN001
    calls = recorder.install(raise_exc=GenerativeJobCancelled())

    result = TASKS[kind](str(uuid4()))

    assert result == "cancelled"
    assert [(c.status, c.fail_reason) for c in calls] == [
        (TaskStatus.RUNNING, None),
        (TaskStatus.CANCELLED, "用户取消"),
    ]


@pytest.mark.parametrize("kind", ["video", "image"])
@pytest.mark.parametrize(
    "exc",
    [GenerativeJobNotFound(uuid4()), RuntimeError("厂商超时")],
    ids=["job-not-found", "generic-error"],
)
def test_failure_paths_are_identical_and_reraise(recorder, kind, exc):  # noqa: ANN001
    """两类异常的终态回写必须一致：RUNNING → FAILED(带原因)，且都原样重抛。"""
    calls = recorder.install(raise_exc=exc)

    with pytest.raises(type(exc)):
        TASKS[kind](str(uuid4()))

    assert [c.status for c in calls] == [TaskStatus.RUNNING, TaskStatus.FAILED]
    assert calls[-1].fail_reason == str(exc)[:2000]


@pytest.mark.parametrize("kind", ["video", "image"])
def test_fail_reason_is_truncated_to_2000_chars(recorder, kind):  # noqa: ANN001
    calls = recorder.install(raise_exc=RuntimeError("x" * 5000))

    with pytest.raises(RuntimeError):
        TASKS[kind](str(uuid4()))

    assert len(calls[-1].fail_reason) == 2000


@pytest.mark.parametrize("kind", ["video", "image"])
def test_failure_does_not_write_success_status(recorder, kind):  # noqa: ANN001
    calls = recorder.install(raise_exc=RuntimeError("boom"))

    with pytest.raises(RuntimeError):
        TASKS[kind](str(uuid4()))

    assert TaskStatus.SUCCESS not in [c.status for c in calls]
