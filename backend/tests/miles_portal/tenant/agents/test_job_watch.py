"""``watch_generative_job`` 轮询推送的特征化测试。

该函数此前无覆盖，但其推送规则相当细：快照未变不推、``queued`` 只在首轮推、
终态推 ``progress`` 后紧接着 ``done`` 且**不** commit、非终态每轮 commit、
连续 120 轮无终态即自行退出。重构前先逐条锁住。
"""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from miles_core.models.model.generative_job import GenerativeJobStatus
from miles_portal.tenant.agents.ws import job_watch
from miles_portal.tenant.agents.ws import protocol as proto
from tests.conftest import make_tenant_ctx

_PENDING = GenerativeJobStatus.PENDING
_RUNNING = GenerativeJobStatus.RUNNING
_SUCCESS = GenerativeJobStatus.SUCCESS


def _job(status, *, progress: int = 0, message: str = "", updated: str = "2026-01-01T00:00:00Z"):  # noqa: ANN001
    return SimpleNamespace(
        id=uuid4(),
        status=status,
        progress_percent=progress,
        progress_message=message,
        updated_at=updated,
    )


class _Session:
    """可检视 commit 次数的 session 假件。"""

    def __init__(self) -> None:
        self.db = AsyncMock()

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, *args):
        return None


class _Ws:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_json(self, data: dict) -> None:
        self.sent.append(data)

    def types(self) -> list[str]:
        return [s["type"] for s in self.sent]


class _FakeJobOut:
    """跳过 pydantic 校验，直接产出 dump 结果。"""

    @staticmethod
    def model_validate(job):  # noqa: ANN001
        return SimpleNamespace(
            model_dump=lambda mode="json": {  # noqa: ARG005
                "id": str(job.id),
                "status": job.status.value,
                "result": None,
                "error_message": None,
            }
        )


@contextmanager
def _watching(jobs, *, error_from: int | None = None):  # noqa: ANN001
    """运行环境：``jobs`` 按轮询次序返回，越界后重复最后一项；yield (ws, sleeps, sessions)。"""
    queue = list(jobs)
    counter = {"i": 0}

    async def fake_get(_db, _ctx, _job_id):
        idx = counter["i"]
        counter["i"] += 1
        if error_from is not None and idx >= error_from:
            raise RuntimeError("db down")
        return queue[min(idx, len(queue) - 1)]

    ws = _Ws()
    sleeps: list[float] = []
    sessions: list[_Session] = []

    async def fake_sleep(seconds):  # noqa: ANN001
        sleeps.append(seconds)

    def make_session():
        session = _Session()
        sessions.append(session)
        return session

    with (
        patch.object(job_watch, "AsyncSessionLocal", make_session),
        patch.object(job_watch, "get_generative_job_for_tenant", fake_get),
        patch.object(job_watch, "GenerativeJobOut", _FakeJobOut),
        patch.object(job_watch, "asyncio", SimpleNamespace(sleep=fake_sleep)),
    ):
        yield ws, sleeps, sessions


# --------------------------------------------------------------------------- #
# 快照去重
# --------------------------------------------------------------------------- #


async def test_unchanged_snapshot_pushes_nothing():
    running = _job(_RUNNING, progress=5)
    done = _job(_SUCCESS, progress=100)

    with _watching([running, running, done]) as (ws, _sleeps, _sessions):
        await job_watch.watch_generative_job(ws, make_tenant_ctx(), uuid4())

    # 第 2 轮快照未变：不推；第 3 轮终态：progress + done
    assert ws.types() == [
        proto.GENERATIVE_JOB_PROGRESS,
        proto.GENERATIVE_JOB_PROGRESS,
        proto.GENERATIVE_JOB_DONE,
    ]


async def test_snapshot_key_includes_updated_at():
    """仅 updated_at 变化也算快照变化，会再推一次。"""
    first = _job(_RUNNING, progress=5, updated="2026-01-01T00:00:00Z")
    second = _job(_RUNNING, progress=5, updated="2026-01-01T00:00:05Z")

    with _watching([first, second, _job(_SUCCESS)]) as (ws, _sleeps, _sessions):
        await job_watch.watch_generative_job(ws, make_tenant_ctx(), uuid4())

    assert ws.types().count(proto.GENERATIVE_JOB_PROGRESS) == 3


# --------------------------------------------------------------------------- #
# queued 只在首轮
# --------------------------------------------------------------------------- #


async def test_pending_on_first_tick_pushes_queued_then_progress():
    pending = _job(_PENDING)

    with _watching([pending, pending, _job(_SUCCESS)]) as (ws, _sleeps, _sessions):
        await job_watch.watch_generative_job(ws, make_tenant_ctx(), uuid4())

    assert ws.types() == [
        proto.GENERATIVE_JOB_QUEUED,
        proto.GENERATIVE_JOB_PROGRESS,
        proto.GENERATIVE_JOB_PROGRESS,
        proto.GENERATIVE_JOB_DONE,
    ]


async def test_pending_after_first_tick_skips_queued():
    with _watching([_job(_RUNNING, progress=5), _job(_PENDING), _job(_SUCCESS)]) as (ws, _sleeps, _sessions):
        await job_watch.watch_generative_job(ws, make_tenant_ctx(), uuid4())

    assert proto.GENERATIVE_JOB_QUEUED not in ws.types()


# --------------------------------------------------------------------------- #
# commit 时机
# --------------------------------------------------------------------------- #


async def test_non_terminal_ticks_commit_terminal_tick_does_not():
    with _watching([_job(_RUNNING, progress=5), _job(_SUCCESS)]) as (_ws, _sleeps, sessions):
        await job_watch.watch_generative_job(_ws, make_tenant_ctx(), uuid4())

    assert len(sessions) == 2
    assert sessions[0].db.commit.await_count == 1
    assert sessions[1].db.commit.await_count == 0


# --------------------------------------------------------------------------- #
# done 载荷与顺序
# --------------------------------------------------------------------------- #


async def test_done_payload_carries_job_snapshot():
    job = _job(_SUCCESS, progress=100)

    with _watching([job]) as (ws, _sleeps, _sessions):
        await job_watch.watch_generative_job(ws, make_tenant_ctx(), uuid4())

    assert ws.types() == [proto.GENERATIVE_JOB_PROGRESS, proto.GENERATIVE_JOB_DONE]
    payload = ws.sent[-1]["payload"]
    assert payload["id"] == str(job.id)
    assert payload["status"] == "success"
    assert payload["result"] is None
    assert payload["error_message"] is None
    assert payload["job"]["id"] == str(job.id)


# --------------------------------------------------------------------------- #
# 异常与上限
# --------------------------------------------------------------------------- #


async def test_poll_error_logs_and_stops_without_frames():
    with _watching([_job(_RUNNING)], error_from=0) as (ws, sleeps, _sessions):
        await job_watch.watch_generative_job(ws, make_tenant_ctx(), uuid4())

    assert ws.types() == []
    assert sleeps == []


async def test_error_after_progress_keeps_earlier_frames():
    with _watching([_job(_RUNNING, progress=5)], error_from=1) as (ws, sleeps, _sessions):
        await job_watch.watch_generative_job(ws, make_tenant_ctx(), uuid4())

    assert ws.types() == [proto.GENERATIVE_JOB_PROGRESS]
    assert sleeps == [1]


async def test_idle_limit_stops_after_120_ticks():
    with _watching([_job(_RUNNING, progress=5)]) as (ws, sleeps, _sessions):
        await job_watch.watch_generative_job(ws, make_tenant_ctx(), uuid4())

    assert len(sleeps) == 120
    assert all(s == 1 for s in sleeps)
    # 快照始终未变，故只在首轮推过一次
    assert ws.types() == [proto.GENERATIVE_JOB_PROGRESS]
