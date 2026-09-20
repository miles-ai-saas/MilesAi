# A2A `tasks/resubscribe` 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让对端在断连后能重新接回仍在进行中的生成任务的进度流（A2A `tasks/resubscribe`，SSE）。

**Architecture:** 把平台既有生成任务订阅循环抽成与协议无关的 `watch_generative_job`（平台 SSE 与 A2A 共用），在其上写一个 A2A 用例层把任务快照映射为 A2A 帧（首帧 `Task`、变化时 `status-update`、终态前补 `artifact-update`、空闲发保活帧），复用既有审计旁路与限流接线。

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy async / redis-py Pub-Sub / SSE / pytest + pytest-asyncio / uv / ruff / import-linter。

**Spec:** `docs/superpowers/specs/2026-09-20-a2a-tasks-resubscribe-design.md`（先读它，本计划只讲「怎么做」）

## Global Constraints

- 所有命令在 `backend/` 下执行，Python 一律用 `uv run python -m ...`（直接 `uv run pytest` 在本仓会撞 `rootdir` 漂移）。
- 测试命令：`uv run python -m pytest -q <paths>`。
- 质量门（Task 6 收尾跑全量）：`uv run ruff check .` / `uv run ruff format --check .` / `uv run python -m pytest -q` / `make layers-check` / `make openapi-check`（后两者在仓库根执行）。
- 注释、docstring、测试名与 commit message 一律**简体中文**；commit 用 Conventional Commits，例如 `feat(a2a): 支持 tasks/resubscribe 续播生成任务进度`。
- **绝不**把消息正文/回答写进 `aud_logs`（租户可见面）；审计只写元数据。
- 既有 `tests/tenant/generative/test_job_stream_events.py` 的 **13 条**断言是重构安全网，**必须原样全绿、不得改动其断言**。
- `miles_portal.tenant.a2a` 是纯逻辑域（`server.py` 无 ORM / 无 DB）；ORM 与 `AsyncSession` 只出现在 `services/` 与 `openapi/views/`。
- 命名与既有风格一致：常量 `UPPER_SNAKE`、模块私有 `_name`、纯函数无副作用。

---

### Task 1: 纯逻辑层新增（帧构造、进度文案、终态判据、时间戳）

**Files:**
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/a2a/server.py`
- Test: `backend/tests/tenant/a2a/test_a2a_server_card.py`（第 1 节「纯函数」）

**Interfaces:**
- Consumes: 无（纯逻辑层，无 DB / 无 ORM）
- Produces:
  - `is_terminal_generative_status(status: object) -> bool`
  - `progress_text(*, progress_message: object, percent: object) -> str | None`
  - `now_iso() -> str`
  - `build_a2a_artifact_update(*, task_id: str, context_id: str | None, artifact: dict, last_chunk: bool = True) -> dict`
  - `build_a2a_status_update(*, task_id, context_id: str | None, state, timestamp, text=None, final=False, job_task_id=None, percent: object = None) -> dict`
  - `build_a2a_agent_message(*, text: str, context_id: str | None, task_id: str | None = None) -> dict`
  - `AUDIT_ACTION_TASKS_RESUBSCRIBE = "a2a.tasks.resubscribe"`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/tenant/a2a/test_a2a_server_card.py` 顶部 import 块补上（放在既有 `from miles_portal.tenant.a2a.server import (...)` 里，保持字母序）：

```python
    build_a2a_artifact_update,
    is_terminal_generative_status,
    now_iso,
    progress_text,
```

同文件 `from datetime import ...` 需新增（该文件当前没有 datetime import）：

```python
from datetime import datetime, timedelta
```

把下面 8 个用例追加到该文件「--- 1. 纯函数 ---」一节的末尾（即 `test_rate_limited_code_is_in_implementation_defined_range` 之后、`# --- 2. 服务：发布门槛 ---` 之前）：

```python
def test_is_terminal_generative_status_only_accepts_known_terminal():
    """未知状态不当作已结束：与 ``to_a2a_task_state`` 回 ``unknown``（而非 ``completed``）同一原则。"""
    assert is_terminal_generative_status("success") is True
    assert is_terminal_generative_status("failed") is True
    assert is_terminal_generative_status("cancelled") is True
    assert is_terminal_generative_status("running") is False
    assert is_terminal_generative_status("pending") is False
    assert is_terminal_generative_status("some-new-state") is False
    assert is_terminal_generative_status(None) is False


def test_is_active_generative_status_is_the_negation_of_terminal():
    """既有判据改为由 ``is_terminal`` 反推：语义逐字不变（含未知状态与 None）。"""
    for status in ("success", "failed", "cancelled", "running", "pending", "some-new-state", None, 3):
        assert is_active_generative_status(status) is (not is_terminal_generative_status(status))


def test_progress_text_prefers_task_message_then_percent():
    assert progress_text(progress_message="45% 渲染中", percent=45) == "45% 渲染中"
    assert progress_text(progress_message="  45% 渲染中  ", percent=45) == "45% 渲染中"
    assert progress_text(progress_message=None, percent=45) == "45%"
    # 两者皆无回 None：调用方据此不附 status.message，而不是塞空串冒充进度
    assert progress_text(progress_message=None, percent=None) is None
    assert progress_text(progress_message="   ", percent=None) is None
    # isinstance(True, int) 为真：不挡布尔会拼出 "True%" 这种脏值
    assert progress_text(progress_message=None, percent=True) is None


def test_build_a2a_artifact_update_shape():
    artifact = {"artifactId": "a1", "parts": [{"kind": "file", "file": {"uri": "https://x/y"}}]}

    event = build_a2a_artifact_update(task_id="t1", context_id="c1", artifact=artifact)

    assert event["kind"] == "artifact-update"
    assert event["taskId"] == "t1"
    assert event["contextId"] == "c1"
    assert event["artifact"] == artifact
    assert event["lastChunk"] is True


def test_build_a2a_artifact_update_omits_absent_context_id():
    """contextId 解析不到就省略：塞空串会让对端拿到一个假的上下文标识（对规范必填要求的有意偏离）。"""
    event = build_a2a_artifact_update(task_id="t1", context_id=None, artifact={"artifactId": "a1"}, last_chunk=False)

    assert "contextId" not in event
    assert event["lastChunk"] is False


def test_build_a2a_status_update_omits_absent_context_id():
    event = build_a2a_status_update(task_id="t1", context_id=None, state="working", timestamp="T", text="写点什么")

    assert "contextId" not in event
    assert "contextId" not in event["status"]["message"]


def test_build_a2a_status_update_carries_percent_beside_job_task_id():
    event = build_a2a_status_update(
        task_id="t1",
        context_id="c1",
        state="working",
        timestamp="T",
        text="45%",
        percent=45,
        job_task_id="job-9",
    )

    assert event["status"]["message"]["metadata"] == {"a2aJobTaskId": "job-9", "percent": 45}


def test_now_iso_is_utc_iso8601():
    parsed = datetime.fromisoformat(now_iso())

    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timedelta(0)
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && uv run python -m pytest -q tests/tenant/a2a/test_a2a_server_card.py -k "terminal or progress_text or artifact_update or percent or now_iso or absent_context"
```

预期：collection error / `ImportError: cannot import name 'is_terminal_generative_status'`（函数与常量都还没定义）。

- [ ] **Step 3: 实现**

`backend/packages/miles-portal/src/miles_portal/tenant/a2a/server.py`：

3a. 顶部 import 增加 `datetime`：

```python
from datetime import UTC, datetime
```

3b. 在 `AUDIT_ACTION_ARTIFACT_DOWNLOAD` 之后加一个动作常量：

```python
AUDIT_ACTION_TASKS_RESUBSCRIBE = "a2a.tasks.resubscribe"
```

3c. 用下面的实现替换既有的 `is_active_generative_status`：

```python
def is_terminal_generative_status(status: object) -> bool:
    """该生成任务是否已到终态（``success`` / ``failed`` / ``cancelled``）。

    只认明确的终态字符串：未知状态视为**未**终态，与 ``to_a2a_task_state`` 对未知回
    ``unknown``（而非 ``completed``）同一原则 —— 宁可让对端多轮询/多收一帧，也不谎称产物已就绪。
    """
    return isinstance(status, str) and status in _TERMINAL_JOB_STATUSES


def is_active_generative_status(status: object) -> bool:
    """该生成任务是否「未到终态」，值得对外返回 ``Task`` 供轮询。

    只是 ``is_terminal_generative_status`` 的反面，判据单一来源。
    """
    return not is_terminal_generative_status(status)
```

3d. 在 `build_a2a_task` 之前加两个纯函数：

```python
def now_iso() -> str:
    """A2A ``TaskStatus.timestamp``（ISO 8601 / UTC）。"""
    return datetime.now(UTC).isoformat()


def progress_text(*, progress_message: object, percent: object) -> str | None:
    """生成任务进度 → 一帧 ``status.message`` 的文本；无话可说时回 ``None``。

    优先任务自带的 ``progress_message``（它通常已含百分比，如「45% 渲染中」），缺失时才用裸
    百分比兜底。两者皆无回 ``None``：调用方据此**不附** ``status.message``，
    而不是塞一个空串冒充进度。
    """
    if isinstance(progress_message, str) and progress_message.strip():
        return progress_message.strip()
    # ``isinstance(True, int)`` 为真：不挡布尔会拼出 "True%" 这种脏值。
    if isinstance(percent, int) and not isinstance(percent, bool):
        return f"{percent}%"
    return None
```

3e. `build_a2a_agent_message` 改为 context_id 可选（唯一改动是 `contextId` 变成条件写入）：

```python
def build_a2a_agent_message(*, text: str, context_id: str | None, task_id: str | None = None) -> dict:
    """A2A ``Message``（agent 角色）。

    ``contextId`` 能取到才回显：解析不到就省略该字段，不塞空串冒充一个假的上下文标识
    （``Task.contextId`` 一贯如此，本函数与它对齐）。
    """
    message: dict = {
        "kind": "message",
        "role": "agent",
        "messageId": str(uuid4()),
        "parts": [{"kind": "text", "text": text}],
    }
    if context_id:
        message["contextId"] = context_id
    if task_id:
        message["taskId"] = task_id
    return message
```

3f. `build_a2a_status_update` 改为 context_id 可选 + 新增 `percent`：

```python
def build_a2a_status_update(
    *,
    task_id: str,
    context_id: str | None,
    state: str,
    timestamp: str,
    text: str | None = None,
    final: bool = False,
    job_task_id: str | None = None,
    percent: object = None,
) -> dict:
    """A2A ``TaskStatusUpdateEvent``（``message/stream`` 与 ``tasks/resubscribe`` 的帧载荷）。

    ``final`` 表示「本流结束」，不等于「任务终态」—— 产生异步生成任务时以
    ``working`` + ``final=True`` 收尾，对端再转向 ``tasks/get`` 轮询。

    ``job_task_id`` 非空时写入嵌套消息的 ``metadata.a2aJobTaskId``：``message/stream`` 的
    taskId 是合成的（流开始时就得定），生成任务 id 只有跑完才知道，故不强行合一，改用该扩展位
    把两者串起来。``percent`` 同理写进 ``metadata.percent``（订阅流的进度百分比）。

    ``contextId`` 解析不到就省略（规范标必填，此处有意偏离，见设计 §3.8）。
    """
    status: dict = {"state": state, "timestamp": timestamp}
    if text is not None:
        message = build_a2a_agent_message(text=text, context_id=context_id, task_id=task_id)
        metadata: dict = {}
        if job_task_id:
            metadata["a2aJobTaskId"] = job_task_id
        if percent is not None:
            metadata["percent"] = percent
        if metadata:
            message["metadata"] = metadata
        status["message"] = message
    event: dict = {
        "kind": "status-update",
        "taskId": task_id,
        "status": status,
        "final": final,
    }
    if context_id:
        event["contextId"] = context_id
    return event
```

3g. 在 `build_a2a_artifacts` 之后加：

```python
def build_a2a_artifact_update(
    *,
    task_id: str,
    context_id: str | None,
    artifact: dict,
    last_chunk: bool = True,
) -> dict:
    """构造 A2A ``TaskArtifactUpdateEvent``（订阅流里「本次产出的新产物」帧）。

    ``artifact`` 直接取 ``build_a2a_artifacts`` 的单项产出（其元素本就是完整的 ``Artifact``），
    故 ``file.uri`` 的拼法仍只有那一处，这里不再重拼。
    """
    event: dict = {
        "kind": "artifact-update",
        "taskId": task_id,
        "artifact": artifact,
        "lastChunk": last_chunk,
    }
    if context_id:
        event["contextId"] = context_id
    return event
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd backend && uv run python -m pytest -q tests/tenant/a2a/test_a2a_server_card.py
```

预期：全绿（含既有 Card / 信封 / 解析用例，证明签名放宽与判据改写无回归）。

- [ ] **Step 5: 提交**

```bash
cd backend && git add packages/miles-portal/src/miles_portal/tenant/a2a/server.py tests/tenant/a2a/test_a2a_server_card.py
git commit -F - <<'EOF'
feat(a2a): 补 tasks/resubscribe 需要的纯逻辑原语

订阅流要发产物帧、进度帧与定时帧，故先补齐帧构造与进度文案；顺带把
is_terminal 判据独立出来（订阅循环需要正向判据），并让 contextId 与既有的
Task 口径一致：解析不到就省略，不塞空串冒充标识。
EOF
```

---

### Task 2: 抽取共用订阅循环 `watch_generative_job`

**Files:**
- Create: `backend/packages/miles-portal/src/miles_portal/tenant/generative/services/job_watch.py`
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/generative/services/job.py:344-399`
- Test: `backend/tests/tenant/generative/test_job_watch.py`（新建）
- 回归：`backend/tests/tenant/generative/test_job_stream_events.py`（**不改一行**）

**Interfaces:**
- Consumes: `miles_common.redis_keys.RedisKeys.generative_job_progress(tenant_id, job_id)`、`miles_core.infra.redis.get_redis`
- Produces: `watch_generative_job(*, job_id: UUID, tenant_id: UUID, reload: Callable[[], Awaitable[GenerativeJob]], is_terminal: Callable[[GenerativeJob], bool], max_seconds: float, poll_interval: float = 1.0, emit_ticks: bool = False) -> AsyncIterator[GenerativeJob | None]`
  - 契约（Task 4 依赖）：**首个产出必是 `reload()` 的快照**；`emit_ticks=True` 时，订阅建立后的每次「没等到消息」的空闲轮询产出 `None`；终态快照产出后即结束。

- [ ] **Step 1: 先跑既有回归测试（确认基线绿）**

```bash
cd backend && uv run python -m pytest -q tests/tenant/generative/test_job_stream_events.py
```

预期：`13 passed`。这是重构安全网；若此处不绿，先停下来查环境。

- [ ] **Step 2: 写失败测试**

新建 `backend/tests/tenant/generative/test_job_watch.py`：

```python
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
    会被它吞掉并转入 DB 回退 —— 守卫实际变成「把 bug 变成降级路径」，用例仍会假通过。
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
```

- [ ] **Step 3: 跑测试确认失败**

```bash
cd backend && uv run python -m pytest -q tests/tenant/generative/test_job_watch.py
```

预期：`ModuleNotFoundError: No module named 'miles_portal.tenant.generative.services.job_watch'`。

- [ ] **Step 4: 实现 watcher**

新建 `backend/packages/miles-portal/src/miles_portal/tenant/generative/services/job_watch.py`：

```python
"""生成任务订阅循环：Redis Pub/Sub 推送 + 兜底终查 + Redis 不可用时回退 DB 轮询。

平台 SSE（``GenerativeJobService.stream_job_events``）与 A2A ``tasks/resubscribe``
共用本模块。两者只在「怎么重新取数」「多久算超时」「空闲要不要产刻度」上不同，故把这些
作为注入项；循环本身只吐 ``GenerativeJob`` 快照，与 SSE、JSON、A2A 全无关。

首个产出契约：**必是 ``reload()`` 的快照**。空闲刻度只会出现在订阅建立**之后**。
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from uuid import UUID

from miles_common.redis_keys import RedisKeys
from miles_core.logging import get_logger
from miles_core.models.model.generative_job import GenerativeJob

logger = get_logger(__name__)


async def watch_generative_job(
    *,
    job_id: UUID,
    tenant_id: UUID,
    reload: Callable[[], Awaitable[GenerativeJob]],
    is_terminal: Callable[[GenerativeJob], bool],
    max_seconds: float,
    poll_interval: float = 1.0,
    emit_ticks: bool = False,
) -> AsyncIterator[GenerativeJob | None]:
    """订阅任务更新直到终态或超时。

    ``poll_interval`` 同时是 ``get_message`` 的阻塞上限、DB 降级路径的刷新间隔与空闲刻度的
    间隔。``emit_ticks=True`` 时，订阅建立后每次空等到点的轮询产出 ``None`` —— 消费方的
    ``async for`` 会一直挂在 ``__anext__`` 上，不给它一个空闲产出点，它就没有机会发保活帧
    （而 ``asyncio.wait_for(anext(...))`` 超时会取消那次 ``anext``、把生成器关掉，不能用）。
    """
    job = await reload()
    yield job
    if is_terminal(job):
        return

    pubsub = None
    channel = None
    try:
        # 必须在函数内 import：单测用 ``monkeypatch.setattr("miles_core.infra.redis.get_redis", …)``
        # 替换源模块属性，模块级 ``from … import get_redis`` 会把替换前的引用固化进来。
        from miles_core.infra.redis import get_redis

        redis = get_redis()
        channel = RedisKeys.generative_job_progress(str(tenant_id), str(job_id))
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel)

        start = time.monotonic()
        terminal_yielded = False
        while time.monotonic() - start < max_seconds:
            # 必须显式传 timeout：redis-py 仅在 timeout 非 None 时阻塞等待、超时返回 None；
            # 省略时默认 0.0 为非阻塞，本循环会空转打满 CPU 直到上限。
            msg = await pubsub.get_message(timeout=poll_interval)
            if msg and msg["type"] == "message":
                job = await reload()
                yield job
                if is_terminal(job):
                    terminal_yielded = True
                    break
            elif emit_ticks:
                yield None
        # 兜底：Pub/Sub 超时或消息丢失时，做一次最终查询避免对端永久等待
        if not terminal_yielded:
            job = await reload()
            if is_terminal(job):
                yield job
    except Exception as exc:
        # Redis 不可用时回退 DB 轮询。此处为宽泛捕获：若失败原因不是「Redis 不可用」
        # （消息序列化错误、下游 bug 等），debug 级在生产不可见、也无消息与堆栈，
        # 整条降级路径等于无据可查，故升为 warning 并带堆栈。
        logger.warning("Redis Pub/Sub 不可用，回退 DB 轮询 (job_id=%s): %s", job_id, exc, exc_info=True)
        idle_ticks = 0
        # 按 ticks 计数而非墙钟：单测把 ``asyncio.sleep`` 换成直通，墙钟上限会变成死循环。
        max_ticks = max(1, int(max_seconds / poll_interval))
        while idle_ticks < max_ticks:
            job = await reload()
            yield job
            if is_terminal(job):
                break
            idle_ticks += 1
            await asyncio.sleep(poll_interval)
    finally:
        if pubsub is not None and channel is not None:
            try:
                await pubsub.unsubscribe(channel)
            except Exception:
                # finally 中的清理动作，失败不应影响收尾，仅 debug 留痕。
                logger.debug("取消订阅 pubsub 失败: channel=%s", channel, exc_info=True)
```

- [ ] **Step 5: 把 `stream_job_events` 改成薄封装**

`backend/packages/miles-portal/src/miles_portal/tenant/generative/services/job.py`：

5a. 删掉 `import asyncio`（重取循环搬走后本模块不再用它；若 Step 6 的 lint 提示仍被别处使用，则保留）。

5b. 在 `_TERMINAL` 常量附近加上两个具名常量（数值与重构前的硬编码一致）：

```python
#: 平台 SSE 的订阅上限与轮询间隔（秒）。与重构前的硬编码值一致 —— 本批只做等价重构。
STREAM_MAX_SECONDS = 120.0
STREAM_POLL_SECONDS = 1.0
```

5c. import 新 watcher：

```python
from miles_portal.tenant.generative.services.job_watch import watch_generative_job
```

5d. 用下面的实现整体替换 `stream_job_events`（第 344-399 行那一段，含原来的 4 条路径）：

```python
    async def stream_job_events(self, job_id: UUID) -> AsyncIterator[str]:
        """SSE：通过 Redis Pub/Sub 推送任务状态/进度，终态后结束。Redis 不可用时自动回退 DB 轮询。

        订阅循环本身（含 Pub/Sub 兜底终查与 Redis 不可用的 DB 回退）在
        ``job_watch.watch_generative_job``：平台 SSE 与 A2A ``tasks/resubscribe`` 共用同一份，
        差别只在注入的重取方式、超时与是否产空闲刻度。
        """
        async for job in watch_generative_job(
            job_id=job_id,
            tenant_id=self.ctx.tenant_id,
            reload=lambda: self._reload(job_id),
            is_terminal=lambda job: job.status in _TERMINAL,
            max_seconds=STREAM_MAX_SECONDS,
            poll_interval=STREAM_POLL_SECONDS,
        ):
            # 本调用未打开 emit_ticks，这里不会收到 None；仍显式挡一道，防后人打开刻度后
            # 静默发出空帧。
            if job is None:
                continue
            yield _sse_frame(job)
```

5e. `_reload` 保持原样留在 `job.py`（它用到本模块命名空间里的 `get_generative_job_for_tenant`，既有回归测试正是替换这个符号，务必不要搬走）：

```python
    async def _reload(self, job_id: UUID) -> GenerativeJob:
        """丢弃会话缓存后按租户重取任务：SSE 每一帧都必须是库中最新状态。"""
        self.db.expire_all()
        return await get_generative_job_for_tenant(self.db, self.ctx, job_id)
```

- [ ] **Step 6: 跑测试确认通过（含安全网）**

```bash
cd backend && uv run python -m pytest -q tests/tenant/generative/
```

预期：`test_job_watch.py` 与 `test_job_stream_events.py`（13 条，**未改动**）全绿。

- [ ] **Step 7: 确认新模块被引用（守卫测试）**

```bash
cd backend && uv run python -m pytest -q tests/test_no_unreferenced_modules.py
```

预期：通过（`job_watch` 被 `job.py` import，无需加白名单）。

- [ ] **Step 8: 提交**

```bash
cd backend && git add packages/miles-portal/src/miles_portal/tenant/generative/services/job_watch.py packages/miles-portal/src/miles_portal/tenant/generative/services/job.py tests/tenant/generative/test_job_watch.py
git commit -F - <<'EOF'
refactor(generative): 抽出共用的生成任务订阅循环

A2A tasks/resubscribe 要接的正是平台 SSE 已有的那套循环（Pub/Sub、兜底终查、
Redis 不可用回退轮询），重建一份会连已知的坑一起复制。既有特征化测试正是为
这次提取预备的，13 条断言一字未改、全部通过。
EOF
```

---

### Task 3: 流式原语与审计调度搬家

**Files:**
- Create: `backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/streaming.py`
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/audit.py`
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/server.py`
- Modify: `backend/tests/tenant/a2a/test_a2a_server_card.py`（只改符号引用与新 import）

**Interfaces:**
- Consumes: Task 1 的 `now_iso`
- Produces:
  - `streaming.sse_frame(payload: dict) -> str`、`streaming.elapsed_ms(started: float) -> int`、`streaming.SSE_HEARTBEAT_FRAME`、`streaming.SSE_HEARTBEAT_SECONDS`
  - `audit.schedule_audit(coro) -> None`、`audit.drain_pending_audits() -> None`、`audit._PENDING_AUDITS`
  - `services/server.py` 的公共化：`parse_task_id`、`load_owned_agent_task`、`context_id_from_job_params`

- [ ] **Step 1: 先跑既有 A2A 回归测试（确认基线绿）**

```bash
cd backend && uv run python -m pytest -q tests/tenant/a2a/
```

预期：全绿。本任务是**纯搬迁**，跑完必须与搬迁前逐条一致。

- [ ] **Step 2: 新建 `services/streaming.py`**

```python
"""A2A 流式响应的公共原语：SSE 帧、保活帧与耗时计时。

``message/stream``（``services/server.py``）与 ``tasks/resubscribe``
（``services/subscription.py``）都要拼 SSE 帧、发保活帧、算 ``durationMs``，故集中在此 ——
否则订阅模块只能 import 兄弟模块的私有符号，比搬过来更差。
"""

from __future__ import annotations

import json
import time

#: 保活帧：SSE 规范规定的注释行，客户端解析器一律忽略。
SSE_HEARTBEAT_FRAME = ": ping\n\n"

#: 等待增量的上限（秒）。超时就发一个 SSE 注释帧保活 —— 一次性路由（tool_agent / flow /
#: 子智能体）在末帧之前可能几分钟不产出任何字节，对端与中间代理会按 idle 超时把连接掐掉。
#: 只服务 ``message/stream``：``tasks/resubscribe`` 的保活节奏即它自己的轮询间隔（更密）。
SSE_HEARTBEAT_SECONDS = 15.0


def sse_frame(payload: dict) -> str:
    """单个 SSE 帧。``ensure_ascii=False`` 让中文按原样出网；JSON 转义保证单行。"""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def elapsed_ms(started: float) -> int:
    """自 ``started``（``time.monotonic()``）起的毫秒数。"""
    return int((time.monotonic() - started) * 1000)
```

- [ ] **Step 3: 把审计调度搬进 `services/audit.py`**

在 `backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/audit.py` 的 import 区加上：

```python
import asyncio
from collections.abc import Coroutine
from typing import Any
```

并在 `write_a2a_audit` 之后追加（注释照搬，说明「为什么必须是独立 task」）：

```python
#: 脱离取消作用域的审计写入 task 的强引用。
#: 审计必须跑在独立 task 里（理由见 ``services/server.py`` 的 ``_stream_turn``）；不持有强引用
#: 的话，task 可能在落库前被 GC 回收，留痕静默丢失。
_PENDING_AUDITS: set[asyncio.Task] = set()


def schedule_audit(coro: Coroutine[Any, Any, None]) -> None:
    """把一次审计写入交给脱离调用方取消作用域的独立 task。**同步**，不 ``await``。"""
    task = asyncio.create_task(coro)
    _PENDING_AUDITS.add(task)
    task.add_done_callback(_PENDING_AUDITS.discard)


async def drain_pending_audits() -> None:
    """等在飞的审计 task 全部落地（测试断言用）。

    只 gather **未完成**的：``gather`` 对已 done 的 task 不会让出控制权；若集合里只剩
    「已完成但 discard 回调尚未执行」的 task，纯靠 ``while 集合非空 + gather 全集`` 会占满
    事件循环（连外层 ``wait_for`` 超时都触发不了）。未完成列表为空即返回 —— 已完成的会由
    done 回调自行从集合剔除，不必在此强清。
    """
    while True:
        pending = [t for t in _PENDING_AUDITS if not t.done()]
        if not pending:
            return
        await asyncio.gather(*pending, return_exceptions=True)
```

（幂等哨兵由各调用点自己持有，见 Task 4 的 `schedule_audit_once` —— 它的 `detail` 形状是订阅特有的，放进本模块只会长出参数化的壳。）

- [ ] **Step 4: 清理 `services/server.py` 并改用新原位**

4a. 删除这些定义（内容已搬走）：`SSE_HEARTBEAT_SECONDS`、`SSE_HEARTBEAT_FRAME`、`_PENDING_AUDITS`、`_schedule_audit`、`drain_pending_audits`、`_sse_frame`、`_now`、`_elapsed_ms`。

4b. 清理因此变空的 import（**必须做**，否则 ruff 报未使用）：`import json`、`from datetime import UTC, datetime`、`collections.abc` 里的 `Coroutine`、`typing` 里的 `Any`。保留 `asyncio` 与 `time`（轮次队列与计时仍在用）。`from typing import Any` 整行删除。

4c. import 区新增：

```python
from miles_portal.tenant.a2a.services import streaming
from miles_portal.tenant.a2a.services.audit import schedule_audit, write_a2a_audit
```

（删掉原来的 `from miles_portal.tenant.a2a.services.audit import write_a2a_audit`；`schedule_audit` 取代 `_schedule_audit`。）

4d. 纯逻辑模块的 import 列表除既有项外**新增** `now_iso`（`_now` 的替代）：

```python
    now_iso,
```

4e. 全文替换调用点（机械替换，逐个确认）：

| 原写法 | 新写法 |
|---|---|
| `_sse_frame(x)` | `streaming.sse_frame(x)` |
| `_now()` | `now_iso()` |
| `_elapsed_ms(x)` | `streaming.elapsed_ms(x)` |
| `_schedule_audit(x)` | `schedule_audit(x)` |
| `SSE_HEARTBEAT_SECONDS` | `streaming.SSE_HEARTBEAT_SECONDS` |
| `SSE_HEARTBEAT_FRAME` | `streaming.SSE_HEARTBEAT_FRAME` |

**心跳与帧原语必须走模块属性**（`streaming.SSE_HEARTBEAT_SECONDS`，不要 `from … import SSE_HEARTBEAT_SECONDS`）：这样单测只有一个 monkeypatch 点。

4f. `_stream_turn` 里那个 `schedule_stream_audit` 内部保留既有写法与注释，仅把 `_schedule_audit(` 改成 `schedule_audit(`，并在其 docstring 第 3 条的「脱离取消作用域」说明里把「交 ``_schedule_audit`` 起独立 task」改为「交 ``services.audit.schedule_audit`` 起独立 task」。

4g. 三个 shared helper 去掉下划线（订阅模块要用；同包内单向依赖，无环）：

- `_parse_task_id` → `parse_task_id`
- `_load_owned_agent_task` → `load_owned_agent_task`
- `_context_id_from_job_params` → `context_id_from_job_params`

改名后，同文件内的调用点（`_handle_tasks_get`、`_handle_tasks_cancel`、`read_task_artifact`）同步更新。`_first_active_job`、`_agent_message`、`_failure_text`、`_rpc_audit_*`、`_stream_audit_detail`、`_audit_stream_preflight`、`_dispatch_a2a_rpc` 保持私有不动。

- [ ] **Step 5: 更新测试里的符号引用**

`backend/tests/tenant/a2a/test_a2a_server_card.py`：

5a. import 区加两个模块别名（放在 `from miles_portal.tenant.a2a.services import server as server_svc` 附近）：

```python
from miles_portal.tenant.a2a.services import audit as audit_svc
from miles_portal.tenant.a2a.services import streaming as streaming_svc
```

5b. 机械替换（共 11 处）：

```bash
cd backend && sed -i '' \
  -e 's/server_svc\.drain_pending_audits/audit_svc.drain_pending_audits/g' \
  -e 's/server_svc\._PENDING_AUDITS/audit_svc._PENDING_AUDITS/g' \
  -e 's/monkeypatch\.setattr(server_svc, "SSE_HEARTBEAT_SECONDS", 0.01, raising=False)/monkeypatch.setattr(streaming_svc, "SSE_HEARTBEAT_SECONDS", 0.01)/' \
  tests/tenant/a2a/test_a2a_server_card.py
```

5c. 确认没有漏网：

```bash
cd backend && rg -n "server_svc\.drain_pending_audits|server_svc\._PENDING_AUDITS|server_svc\.SSE_HEARTBEAT" tests/ ; echo "exit=$?"
```

预期：无输出、`exit=1`。

- [ ] **Step 6: 跑测试确认仍是纯搬迁**

```bash
cd backend && uv run python -m pytest -q tests/tenant/a2a/ tests/tenant/generative/
```

预期：全绿，且**用例数与搬迁前完全一致**（无新增、无删除）。

- [ ] **Step 7: 提交**

```bash
cd backend && git add packages/miles-portal/src/miles_portal/tenant/a2a/services/ tests/tenant/a2a/test_a2a_server_card.py
git commit -F - <<'EOF'
refactor(a2a): 流式原语与审计调度迁到共用位置

订阅用例要拼 SSE 帧、发保活帧、按取消作用域之外补留痕，若去 import 兄弟模块的
私有符号，依赖方向就反了。纯搬迁，无行为变更；顺带把订阅要复用的三个任务寻址
helper 去掉下划线（它们本就是 tasks/* 的共用入口）。
EOF
```

---

### Task 4: 订阅用例层 `open_task_subscription`

**Files:**
- Create: `backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/subscription.py`
- Test: `backend/tests/tenant/a2a/test_a2a_task_resubscribe.py`（新建）

**Interfaces:**
- Consumes: Task 1 的纯逻辑函数、Task 2 的 `watch_generative_job`、Task 3 的 `streaming` / `schedule_audit` / `parse_task_id` / `load_owned_agent_task` / `context_id_from_job_params`
- Produces: `open_task_subscription(db, ctx, agent_id, payload, *, base_url) -> dict | AsyncIterator[str]`
  - `dict` = 不要进入 SSE（前置校验失败的 JSON-RPC 错误信封）
  - `AsyncIterator[str]` = SSE 帧流

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/tenant/a2a/test_a2a_task_resubscribe.py`：

```python
"""A2A ``tasks/resubscribe`` 服务层：帧序列、去重、安全上限、断连留痕。

只覆盖订阅用例本身：订阅循环在 ``tests/tenant/generative/test_job_watch.py``，
纯逻辑在 ``test_a2a_server_card.py``。此处把 watcher 换成脚本化假实现，
从而精确控制「第几帧发生什么」。
"""

from __future__ import annotations

import asyncio
import json
import logging
from types import SimpleNamespace
from uuid import uuid4

import pytest

from miles_common.exceptions import NotFoundError
from miles_core.models.agent import Agent, AgentStatus, AgentType
from miles_core.tenant import TenantContext
from miles_portal.tenant.a2a import server as server_mod
from miles_portal.tenant.a2a.server import A2A_PUBLISH_FLAG
from miles_portal.tenant.a2a.services import audit as audit_svc
from miles_portal.tenant.a2a.services import server as server_svc
from miles_portal.tenant.a2a.services import subscription as subscription_svc

AGENT_ID = uuid4()
ATTACHMENT_ID = uuid4()
BASE = "https://miles.example.com"
JOB_ID = uuid4()


def _ctx() -> TenantContext:
    return TenantContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        username="a2a-peer",
        is_superuser=False,
        permissions=frozenset({"agent:read"}),
        auth_via="api_key",
        api_key_id=uuid4(),
    )


def _agent():
    agent = Agent()
    agent.id = AGENT_ID
    agent.name = "客服助手"
    agent.description = "D"
    agent.agent_type = AgentType.CUSTOM
    agent.status = AgentStatus.ENABLED
    agent.config = {A2A_PUBLISH_FLAG: True}
    agent.deleted_at = None
    return agent


class _Db:
    """最小 fake：``get`` 返回预置智能体，``commit`` 计数。"""

    def __init__(self, agent=None):  # noqa: ANN001
        self._agent = agent
        self.committed = 0

    async def get(self, _model, _id):  # noqa: ANN001
        return self._agent

    async def commit(self):  # noqa: ANN001
        self.committed += 1


def _job(status: str, *, progress_message=None, progress_percent=None, result=None, params=None):  # noqa: ANN001, ANN202
    """生成任务替身：订阅用例只用这几个字段。"""
    return SimpleNamespace(
        id=JOB_ID,
        tenant_id=uuid4(),
        status=SimpleNamespace(value=status),
        progress_message=progress_message,
        progress_percent=progress_percent,
        result=result,
        params=params if params is not None else {},
    )


def _params(*, task_id=JOB_ID, method="tasks/resubscribe") -> dict:
    return {"jsonrpc": "2.0", "id": 1, "method": method, "params": {"id": str(task_id)}}


def _scripted(script):  # noqa: ANN001, ANN202
    """把「任务快照 / None / 异常」的脚本变成假的 ``watch_generative_job``。"""

    async def fake(**_kwargs):  # noqa: ANN003
        for item in script:
            if isinstance(item, Exception):
                raise item
            yield item

    return fake


async def _raw_frames(stream) -> list[str]:  # noqa: ANN001
    return [frame async for frame in stream]


async def _json_frames(stream) -> list[dict]:  # noqa: ANN001
    """只取数据帧（保活帧是 SSE 注释行，不进 JSON 序列）。"""
    return [json.loads(f[len("data: ") : -2]) for f in await _raw_frames(stream) if f.startswith("data: ")]


@pytest.fixture(autouse=True)
def audit_recorder(monkeypatch):  # noqa: ANN001
    """审计走独立会话，单测不连库：替换 ``subscription`` 命名空间里的写入函数。"""
    recorded: list[dict] = []

    async def fake_write(**kwargs):  # noqa: ANN003
        # 让出一次控制权：真实写库必然挂起，取消时序的敏感性只有这样才测得出来
        await asyncio.sleep(0)
        recorded.append(kwargs)

    monkeypatch.setattr(subscription_svc, "write_a2a_audit", fake_write)
    return recorded


@pytest.fixture
def owned_job(monkeypatch):  # noqa: ANN001
    """让归属校验通过：``load_owned_agent_task`` 取到一个属于本智能体的任务。"""

    def _set(job):  # noqa: ANN001
        job.source_ref_type = "agent"
        job.source_ref_id = AGENT_ID

        async def _get(_db, _ctx, _job_id):  # noqa: ANN001
            return job

        # 打的是 server 模块的命名空间：归属校验函数定义在那里
        monkeypatch.setattr(server_svc, "get_generative_job_for_tenant", _get)
        return job

    return _set


# --- 前置校验 --------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_preflight_rejects_unpublished_agent_and_audits_failure(audit_recorder, monkeypatch):  # noqa: ANN001
    def fail_watch(**_kwargs):  # noqa: ANN003
        raise AssertionError("前置校验失败时不应搭起订阅循环")

    monkeypatch.setattr(subscription_svc, "watch_generative_job", fail_watch)

    opened = await subscription_svc.open_task_subscription(_Db(agent=None), _ctx(), AGENT_ID, _params(), base_url=BASE)

    assert isinstance(opened, dict)
    # 与 message/stream 的智能体门槛同口径：未发布回参数类错误码，而不是「任务不存在」
    assert opened["error"]["code"] == server_mod.INVALID_PARAMS
    assert len(audit_recorder) == 1
    assert audit_recorder[0]["action"] == server_mod.AUDIT_ACTION_TASKS_RESUBSCRIBE
    assert audit_recorder[0]["outcome"] == server_mod.AUDIT_OUTCOME_FAILED
    assert audit_recorder[0]["detail"]["errorCode"] == server_mod.INVALID_PARAMS
    # 前置失败没有流，故 detail 里不该出现只有收流才有的时间线字段
    assert "endedBy" not in audit_recorder[0]["detail"]


@pytest.mark.asyncio
async def test_preflight_rejects_bad_task_id_and_audits_invalid_params(audit_recorder):  # noqa: ANN001
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tasks/resubscribe", "params": {"id": "not-a-uuid"}}

    opened = await subscription_svc.open_task_subscription(_Db(agent=_agent()), _ctx(), AGENT_ID, payload, base_url=BASE)

    assert isinstance(opened, dict)
    assert opened["error"]["code"] == server_mod.INVALID_PARAMS
    assert audit_recorder[0]["detail"]["errorCode"] == server_mod.INVALID_PARAMS


@pytest.mark.asyncio
async def test_preflight_rejects_foreign_or_missing_task_with_task_not_found(audit_recorder, owned_job, monkeypatch):  # noqa: ANN001
    """不属于该智能体、或根本不存在（含合成流式 id）：一律 ``-32001``，不确认任务是否存在。"""
    job = owned_job(_job("running"))
    job.source_ref_id = uuid4()

    opened = await subscription_svc.open_task_subscription(_Db(agent=_agent()), _ctx(), AGENT_ID, _params(), base_url=BASE)
    assert isinstance(opened, dict)
    assert opened["error"]["code"] == server_mod.TASK_NOT_FOUND
    assert audit_recorder[0]["detail"]["errorCode"] == server_mod.TASK_NOT_FOUND

    async def _missing(_db, _ctx, _job_id):  # noqa: ANN001
        raise NotFoundError("生成任务不存在")

    monkeypatch.setattr(server_svc, "get_generative_job_for_tenant", _missing)

    missing = await subscription_svc.open_task_subscription(_Db(agent=_agent()), _ctx(), AGENT_ID, _params(task_id=uuid4()), base_url=BASE)
    assert isinstance(missing, dict)
    assert missing["error"]["code"] == server_mod.TASK_NOT_FOUND
    assert len(audit_recorder) == 2
    assert audit_recorder[1]["detail"]["method"] == "tasks/resubscribe"


# --- 帧序列 ----------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_frames_follow_deduped_task_status_artifact_terminal(monkeypatch, audit_recorder, owned_job):  # noqa: ANN001
    """首帧 Task → 变化才发 status-update → 产物帧 → 终态帧（final=true）。"""
    job = owned_job(_job("running", progress_message="10%", params={"conversation_id": "ctx-7"}))
    done = _job(
        "success",
        progress_message="已完成",
        progress_percent=100,
        result={"attachment_id": str(ATTACHMENT_ID), "mime_type": "video/mp4", "kind": "video"},
    )
    script = [job, _job("running", progress_message="10%"), _job("running", progress_message="60%"), done]
    monkeypatch.setattr(subscription_svc, "watch_generative_job", _scripted(script))

    opened = await subscription_svc.open_task_subscription(_Db(agent=_agent()), _ctx(), AGENT_ID, _params(), base_url=BASE)
    # 帧只消费一次：先收全，再分别从数据帧与注释帧里取断言素材
    raw = await _raw_frames(opened)
    results = [json.loads(f[len("data: ") : -2])["result"] for f in raw if f.startswith("data: ")]

    assert results[0]["kind"] == "task"
    assert results[0]["status"]["state"] == "working"
    assert results[0]["contextId"] == "ctx-7"
    assert "artifacts" not in results[0]

    mids = results[1:-2]
    assert [m["status"]["message"]["parts"][0]["text"] for m in mids] == ["60%"]
    assert mids[0]["final"] is False

    artifact = results[-2]
    assert artifact["kind"] == "artifact-update"
    assert artifact["artifact"]["artifactId"] == str(ATTACHMENT_ID)
    assert artifact["artifact"]["parts"][0]["file"]["uri"] == f"{BASE}/api/v1/open/a2a/agents/{AGENT_ID}/tasks/{JOB_ID}/artifacts/{ATTACHMENT_ID}"

    last = results[-1]
    assert last["kind"] == "status-update"
    assert last["status"]["state"] == "completed"
    assert last["final"] is True

    # 无变化的那一帧换成了保活注释帧
    assert any(frame.startswith(":") for frame in raw)

    await audit_svc.drain_pending_audits()
    assert len(audit_recorder) == 1
    assert audit_recorder[0]["detail"]["endedBy"] == "terminal"
    assert audit_recorder[0]["detail"]["taskState"] == "completed"
    assert audit_recorder[0]["outcome"] == server_mod.AUDIT_OUTCOME_OK
    assert audit_recorder[0]["detail"]["taskId"] == str(JOB_ID)
    assert audit_recorder[0]["detail"]["contextId"] == "ctx-7"


@pytest.mark.asyncio
async def test_progress_frame_carries_percent_in_message_metadata(monkeypatch, owned_job):  # noqa: ANN001
    job = owned_job(_job("running", progress_message="渲染中", progress_percent=45))
    monkeypatch.setattr(
        subscription_svc,
        "watch_generative_job",
        _scripted([job, _job("running", progress_message="渲染中", progress_percent=46)]),
    )

    opened = await subscription_svc.open_task_subscription(_Db(agent=_agent()), _ctx(), AGENT_ID, _params(), base_url=BASE)
    results = [f["result"] for f in await _json_frames(opened)]

    assert results[1]["status"]["message"]["parts"][0]["text"] == "渲染中"
    assert results[1]["status"]["message"]["metadata"] == {"percent": 46}


@pytest.mark.asyncio
async def test_already_terminal_subscription_puts_artifacts_in_first_frame(monkeypatch, audit_recorder, owned_job):  # noqa: ANN001
    """订阅时已终态：产物挂首帧，且**不**再发 artifact-update（同一条流里不重复出现）。"""
    done = owned_job(
        _job(
            "success",
            progress_message="已完成",
            result={"attachment_ids": [str(ATTACHMENT_ID)], "mime_type": "image/png", "kind": "image"},
        )
    )
    monkeypatch.setattr(subscription_svc, "watch_generative_job", _scripted([done]))

    opened = await subscription_svc.open_task_subscription(_Db(agent=_agent()), _ctx(), AGENT_ID, _params(), base_url=BASE)
    results = [f["result"] for f in await _json_frames(opened)]

    assert [r["kind"] for r in results] == ["task", "status-update"]
    assert results[0]["artifacts"][0]["artifactId"] == str(ATTACHMENT_ID)
    assert results[-1]["final"] is True and results[-1]["status"]["state"] == "completed"

    await audit_svc.drain_pending_audits()
    assert audit_recorder[0]["detail"]["endedBy"] == "terminal"


@pytest.mark.asyncio
async def test_omits_context_id_when_unresolvable(monkeypatch, owned_job):  # noqa: ANN001
    """``contextId`` 解析不到就省略（对规范必填要求的有意偏离，见设计 §3.8）。"""
    monkeypatch.setattr(subscription_svc, "watch_generative_job", _scripted([owned_job(_job("running", progress_message="跑着"))]))

    opened = await subscription_svc.open_task_subscription(_Db(agent=_agent()), _ctx(), AGENT_ID, _params(), base_url=BASE)
    results = [f["result"] for f in await _json_frames(opened)]

    assert all("contextId" not in frame for frame in results)
    assert all("contextId" not in frame["status"].get("message", {}) for frame in results)


@pytest.mark.asyncio
async def test_safety_cap_closes_with_real_state_and_final(monkeypatch, audit_recorder, owned_job):  # noqa: ANN001
    """watcher 结束而任务仍未终态：以真实状态 + ``final=true`` 收流，不谎报 completed。"""
    monkeypatch.setattr(subscription_svc, "watch_generative_job", _scripted([owned_job(_job("pending"))]))

    opened = await subscription_svc.open_task_subscription(_Db(agent=_agent()), _ctx(), AGENT_ID, _params(), base_url=BASE)
    results = [f["result"] for f in await _json_frames(opened)]

    assert results[0]["status"]["state"] == "submitted"
    assert results[-1]["final"] is True
    assert results[-1]["status"]["state"] == "submitted"

    await audit_svc.drain_pending_audits()
    assert audit_recorder[0]["detail"]["endedBy"] == "safety-cap"
    assert audit_recorder[0]["outcome"] == server_mod.AUDIT_OUTCOME_OK


@pytest.mark.asyncio
async def test_safety_cap_logs_warning_for_diagnosability(monkeypatch, caplog, owned_job):  # noqa: ANN001
    """30 分钟上限是对规范的有意偏离：审计行只在租户审计页可见，故日志侧也必须留痕，
    否则「病态任务占住连接半小时」在运维侧完全不可见。"""
    monkeypatch.setattr(subscription_svc, "watch_generative_job", _scripted([owned_job(_job("pending"))]))

    with caplog.at_level(logging.WARNING, logger="miles_portal.tenant.a2a.services.subscription"):
        opened = await subscription_svc.open_task_subscription(_Db(agent=_agent()), _ctx(), AGENT_ID, _params(), base_url=BASE)
        await _json_frames(opened)

    records = [r for r in caplog.records if r.name == "miles_portal.tenant.a2a.services.subscription"]
    # 恰好一条：正常收流路径只此一处 warning，多一条就说明有新噪音
    assert len(records) == 1
    assert records[0].levelno == logging.WARNING
    # 关键定位字段齐全（agent_id / task_id 至少要有）
    assert str(AGENT_ID) in records[0].getMessage()
    assert str(JOB_ID) in records[0].getMessage()
    assert "安全上限" in records[0].getMessage()


@pytest.mark.asyncio
async def test_canceled_job_audits_ok_and_reports_task_state(monkeypatch, audit_recorder, owned_job):  # noqa: ANN001
    """任务被取消是合法终态：outcome 记 ``ok``（``canceled`` 这一 outcome 专指对端断连）。"""
    monkeypatch.setattr(
        subscription_svc,
        "watch_generative_job",
        _scripted([owned_job(_job("running")), _job("cancelled", progress_message="已取消")]),
    )

    opened = await subscription_svc.open_task_subscription(_Db(agent=_agent()), _ctx(), AGENT_ID, _params(), base_url=BASE)
    results = [f["result"] for f in await _json_frames(opened)]

    assert results[-1]["status"]["state"] == "canceled"

    await audit_svc.drain_pending_audits()
    assert audit_recorder[0]["outcome"] == server_mod.AUDIT_OUTCOME_OK
    assert audit_recorder[0]["detail"]["taskState"] == "canceled"
    assert audit_recorder[0]["detail"]["endedBy"] == "terminal"


# --- 断连与异常 ------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_disconnect_audits_canceled_exactly_once(monkeypatch, audit_recorder, owned_job):  # noqa: ANN001
    """对端中途掐断连接：恰好一条 ``canceled`` 流水，且带断连前的状态。"""
    monkeypatch.setattr(subscription_svc, "watch_generative_job", _scripted([owned_job(_job("running")), _job("running", progress_message="60%")]))

    opened = await subscription_svc.open_task_subscription(_Db(agent=_agent()), _ctx(), AGENT_ID, _params(), base_url=BASE)
    assert await anext(opened) is not None  # 首帧 Task

    await opened.aclose()

    await audit_svc.drain_pending_audits()
    assert len(audit_recorder) == 1
    assert audit_recorder[0]["outcome"] == server_mod.AUDIT_OUTCOME_CANCELED
    assert audit_recorder[0]["detail"]["endedBy"] == "disconnect"
    assert audit_recorder[0]["detail"]["taskState"] == "working"


@pytest.mark.asyncio
async def test_watcher_error_emits_failed_terminal_frame_and_audits(monkeypatch, audit_recorder, owned_job):  # noqa: ANN001
    """订阅中途的非预期异常（任务被删等）：回终态帧再收流，绝不无声断流。"""
    monkeypatch.setattr(
        subscription_svc,
        "watch_generative_job",
        _scripted([owned_job(_job("running")), RuntimeError("任务已被删除")]),
    )

    opened = await subscription_svc.open_task_subscription(_Db(agent=_agent()), _ctx(), AGENT_ID, _params(), base_url=BASE)
    results = [f["result"] for f in await _json_frames(opened)]

    assert results[-1]["final"] is True
    assert results[-1]["status"]["state"] == "failed"

    await audit_svc.drain_pending_audits()
    assert audit_recorder[0]["outcome"] == server_mod.AUDIT_OUTCOME_FAILED
    assert audit_recorder[0]["detail"]["endedBy"] == "failed"


@pytest.mark.asyncio
async def test_commit_releases_request_scoped_connection(monkeypatch, owned_job):  # noqa: ANN001
    """通过前置校验后立刻结束请求级事务：30 分钟的流不能让一条连接陪跑。"""
    monkeypatch.setattr(subscription_svc, "watch_generative_job", _scripted([owned_job(_job("running"))]))
    db = _Db(agent=_agent())

    await subscription_svc.open_task_subscription(db, _ctx(), AGENT_ID, _params(), base_url=BASE)

    assert db.committed == 1
```

> 实现者注意：`_raw_frames` 与 `_json_frames` 都会**耗尽**生成器，同一个流不能既 `_raw_frames`
> 又 `_json_frames`；需要同时断言数据帧与保活帧时，用 `_raw_frames` 收全后自行过滤（见上面那条用例）。

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && uv run python -m pytest -q tests/tenant/a2a/test_a2a_task_resubscribe.py
```

预期：`ModuleNotFoundError: No module named 'miles_portal.tenant.a2a.services.subscription'`。

- [ ] **Step 3: 实现订阅用例层**

新建 `backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/subscription.py`：

```python
"""A2A ``tasks/resubscribe`` 用例层：把生成任务进度续播为 SSE 帧。

与 ``message/stream``（``services/server.py``）方向相同、来源不同：那边跑一轮对话并把 token
逐片下发，这边**不产生**任何内容，只把平台既有的生成任务进度（Redis Pub/Sub）转成 A2A 帧。
故它复用 ``services/streaming`` 的帧原语、``services/audit`` 的旁路留痕，以及
``generative.services.job_watch`` 的订阅循环。

可续播范围：只认真实生成任务 id（``params.id`` 即 job id）。``message/stream`` 的合成
``taskId`` 不落库，拿它来订阅会按「任务不存在」回 ``-32001``。
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.exceptions import BadRequestError, NotFoundError
from miles_core.infra.db import AsyncSessionLocal
from miles_core.logging import get_logger
from miles_core.models.model.generative_job import GenerativeJob
from miles_core.tenant import TenantContext
from miles_portal.tenant.a2a.server import (
    AUDIT_ACTION_TASKS_RESUBSCRIBE,
    AUDIT_OUTCOME_CANCELED,
    AUDIT_OUTCOME_FAILED,
    AUDIT_OUTCOME_OK,
    INVALID_PARAMS,
    INVALID_REQUEST,
    TASK_NOT_FOUND,
    TASK_STATE_CANCELED,
    TASK_STATE_COMPLETED,
    TASK_STATE_FAILED,
    TASK_STATE_UNKNOWN,
    build_a2a_artifact_update,
    build_a2a_artifacts,
    build_a2a_status_update,
    build_a2a_task,
    is_terminal_generative_status,
    jsonrpc_error,
    jsonrpc_result,
    now_iso,
    progress_text,
    to_a2a_task_state,
)
from miles_portal.tenant.a2a.services import streaming
from miles_portal.tenant.a2a.services.audit import schedule_audit, write_a2a_audit
from miles_portal.tenant.a2a.services.server import (
    context_id_from_job_params,
    load_owned_agent_task,
    load_published_agent,
    parse_task_id,
)
from miles_portal.tenant.generative.services.job_execution import get_generative_job_for_tenant
from miles_portal.tenant.generative.services.job_watch import watch_generative_job

logger = get_logger(__name__)

#: 订阅流的轮询间隔（秒）：``get_message`` 的阻塞上限、DB 降级路径的刷新间隔、空闲刻度间隔。
#: Pub/Sub 有消息时立即返回、不受它影响，故它实际决定的是**保活节奏**与降级路径的取数频率。
SUBSCRIPTION_POLL_SECONDS = 2.0

#: 订阅的安全上限（秒）。规范要求流在 interrupted/terminal 状态结束，到点仍在跑就是**有意偏离**：
#: 病态任务不该无限占住连接。对端可据此再订阅一次（见 docs/guides/a2a.md）。
SUBSCRIPTION_MAX_SECONDS = 1800.0

#: 终态 → 审计 outcome。``canceled`` 记 ``ok``：任务被取消是合法终态、订阅正常走完；
#: ``canceled`` 这一 outcome 本设计里专指「对端断连」，混用会让两者不可区分。
_TERMINAL_OUTCOME = {
    TASK_STATE_COMPLETED: AUDIT_OUTCOME_OK,
    TASK_STATE_CANCELED: AUDIT_OUTCOME_OK,
    TASK_STATE_FAILED: AUDIT_OUTCOME_FAILED,
}


def _progress_fingerprint(job: GenerativeJob) -> tuple[str, object, object]:
    """进度指纹（A2A 状态 + 进度文字 + 百分比）：三者全同即「对端没有新信息」。"""
    return (to_a2a_task_state(str(job.status.value)), job.progress_message, job.progress_percent)


async def open_task_subscription(
    db: AsyncSession,
    ctx: TenantContext,
    agent_id: UUID,
    payload: object,
    *,
    base_url: str,
) -> dict | AsyncIterator[str]:
    """``tasks/resubscribe`` 入口：前置校验失败回 JSON-RPC 错误信封，通过则回 SSE 帧迭代器。

    返回 ``dict`` 而非抛异常，是因为调用方（视图层）要据此决定**不进入 SSE**：一旦响应头写成
    ``text/event-stream``，HTTP 状态与 ``Retry-After`` 就都没处放了。

    前置失败一律先留一条审计再回信封：这些调用没有流，终态帧的审计路径不会走到。
    """
    started = time.monotonic()
    req_id: object = payload.get("id") if isinstance(payload, dict) else None
    if not isinstance(payload, dict) or "method" not in payload:
        await _audit_failure(ctx, agent_id, INVALID_REQUEST, started)
        return jsonrpc_error(req_id, INVALID_REQUEST, "非法 JSON-RPC 请求")
    params = payload.get("params")
    if not isinstance(params, dict):
        await _audit_failure(ctx, agent_id, INVALID_PARAMS, started)
        return jsonrpc_error(req_id, INVALID_PARAMS, "tasks/resubscribe 缺少 params")
    try:
        await load_published_agent(db, agent_id)
    except NotFoundError as exc:
        # 与 message/stream 的智能体门槛同口径：未发布 / 不存在都回参数类错误码，
        # 而不是「任务不存在」—— 后者会把「智能体没发布」误报成「任务找不到」。
        await _audit_failure(ctx, agent_id, INVALID_PARAMS, started)
        return jsonrpc_error(req_id, INVALID_PARAMS, str(exc))
    try:
        job_id = parse_task_id(params)
        job = await load_owned_agent_task(db, ctx, agent_id, job_id)
    except BadRequestError as exc:
        await _audit_failure(ctx, agent_id, INVALID_PARAMS, started)
        return jsonrpc_error(req_id, INVALID_PARAMS, str(exc))
    except NotFoundError as exc:
        # 不区分「不存在 / 不属于该智能体 / 是合成的流式 id」：一律按任务不存在回，不向对端
        # 确认任务是否存在。
        await _audit_failure(ctx, agent_id, TASK_NOT_FOUND, started)
        return jsonrpc_error(req_id, TASK_NOT_FOUND, str(exc))
    # 结束请求级事务并归还连接：订阅最长 30 分钟，不主动结束就会有一条连接陪跑。
    # 用 ``commit`` 而非 ``rollback``：鉴权依赖在同一会话里 flush 了 API Key 的
    # ``last_used_at``（``touch_last_used`` 的契约就是「由调用方提交」），rollback 会把
    # 这笔记账丢掉。
    await db.commit()
    return _subscription_frames(
        ctx=ctx,
        agent_id=agent_id,
        req_id=req_id,
        base_url=base_url,
        job_id=job_id,
        context_id=context_id_from_job_params(job.params),
        started=started,
    )


async def _audit_failure(ctx: TenantContext, agent_id: UUID, error_code: int, started: float) -> None:
    """前置失败的留痕，口径与 ``message/stream`` 的 ``_audit_stream_preflight`` 一致。

    不记就出现「同一个非法调用，``message/send`` / ``message/stream`` 有迹、
    ``tasks/resubscribe`` 零痕迹」，探测式调用可以不留痕迹。
    """
    await write_a2a_audit(
        ctx=ctx,
        agent_id=agent_id,
        action=AUDIT_ACTION_TASKS_RESUBSCRIBE,
        outcome=AUDIT_OUTCOME_FAILED,
        detail={
            "method": "tasks/resubscribe",
            "errorCode": error_code,
            "durationMs": streaming.elapsed_ms(started),
        },
    )


async def _subscription_frames(
    *,
    ctx: TenantContext,
    agent_id: UUID,
    req_id: object,
    base_url: str,
    job_id: UUID,
    context_id: str | None,
    started: float,
) -> AsyncIterator[str]:
    """订阅帧生成器：首帧 ``Task`` 快照，其后只在确有变化时发帧，其余发保活帧。"""
    #: 本方法的 taskId 就是真实 job id（与 message/stream 的合成 id 不同）
    task_id = str(job_id)
    latest_state = TASK_STATE_UNKNOWN
    audit_state: dict[str, str] = {}

    def schedule_audit_once(audit_outcome: str, *, ended_by: str, task_state: str) -> None:
        """调度本次订阅的留痕：同步、幂等、脱离取消作用域。

        三条缺一不可，理由与 ``message/stream`` 的 ``schedule_stream_audit`` 完全相同
        （见 ``services/server.py`` 的注释），差别只在 ``detail`` 多 ``endedBy`` / ``taskState``。
        """
        if audit_state:
            return
        audit_state["outcome"] = audit_outcome
        detail: dict = {
            "method": "tasks/resubscribe",
            "taskId": task_id,
            "taskState": task_state,
            "endedBy": ended_by,
            "durationMs": streaming.elapsed_ms(started),
        }
        if context_id:
            detail["contextId"] = context_id
        schedule_audit(
            write_a2a_audit(
                ctx=ctx,
                agent_id=agent_id,
                action=AUDIT_ACTION_TASKS_RESUBSCRIBE,
                outcome=audit_outcome,
                detail=detail,
            )
        )

    def status_frame(*, state: str, text: str | None, percent: object, final: bool) -> str:
        return streaming.sse_frame(
            jsonrpc_result(
                req_id,
                build_a2a_status_update(
                    task_id=task_id,
                    context_id=context_id,
                    state=state,
                    timestamp=now_iso(),
                    text=text,
                    final=final,
                    percent=percent,
                ),
            )
        )

    async def reload_job() -> GenerativeJob:
        # 短开短关：30 分钟上限下绝不能让一条连接陪跑整段流（与 message/stream 的轮次会话同法）。
        async with AsyncSessionLocal() as session:
            return await get_generative_job_for_tenant(session, ctx, job_id)

    jobs = watch_generative_job(
        job_id=job_id,
        tenant_id=ctx.tenant_id,
        reload=reload_job,
        is_terminal=lambda job: is_terminal_generative_status(str(job.status.value)),
        max_seconds=SUBSCRIPTION_MAX_SECONDS,
        poll_interval=SUBSCRIPTION_POLL_SECONDS,
        emit_ticks=True,
    )
    try:
        first = await anext(jobs)
        if first is None:
            # 契约保证走不到：刻度只在订阅建立**之后**产出，首产出必是 reload 快照。
            # 真走到说明契约被改坏，按「拿不到快照」收尾，不让内部错误变成 500。
            schedule_audit_once(AUDIT_OUTCOME_FAILED, ended_by="failed", task_state=TASK_STATE_UNKNOWN)
            return
        latest_job = first
        latest_state = to_a2a_task_state(str(first.status.value))
        terminal_at_subscribe = is_terminal_generative_status(str(first.status.value))
        yield streaming.sse_frame(
            jsonrpc_result(
                req_id,
                build_a2a_task(
                    task_id=task_id,
                    context_id=context_id,
                    state=latest_state,
                    timestamp=now_iso(),
                    # 订阅时已终态：产物直接挂首帧（一帧讲完整段故事）；否则本次订阅期间产出的
                    # 走 artifact-update 帧，同一产物不在一条流里出现两次。
                    artifacts=(
                        build_a2a_artifacts(job_result=first.result, agent_id=agent_id, task_id=job_id, base_url=base_url) if terminal_at_subscribe else None
                    ),
                ),
            )
        )
        if terminal_at_subscribe:
            schedule_audit_once(
                _TERMINAL_OUTCOME.get(latest_state, AUDIT_OUTCOME_FAILED),
                ended_by="terminal",
                task_state=latest_state,
            )
            yield status_frame(
                state=latest_state,
                text=progress_text(progress_message=first.progress_message, percent=first.progress_percent),
                percent=first.progress_percent,
                final=True,
            )
            return

        fingerprint = _progress_fingerprint(first)
        async for job in jobs:
            if job is None:
                # 空闲刻度：下发保活帧（SSE 注释行），对端与中间代理据此知道连接还活着。
                yield streaming.SSE_HEARTBEAT_FRAME
                continue
            latest_job = job
            latest_state = to_a2a_task_state(str(job.status.value))
            if is_terminal_generative_status(str(job.status.value)):
                for artifact in build_a2a_artifacts(job_result=job.result, agent_id=agent_id, task_id=job_id, base_url=base_url):
                    yield streaming.sse_frame(
                        jsonrpc_result(
                            req_id,
                            build_a2a_artifact_update(task_id=task_id, context_id=context_id, artifact=artifact),
                        )
                    )
                schedule_audit_once(
                    _TERMINAL_OUTCOME.get(latest_state, AUDIT_OUTCOME_FAILED),
                    ended_by="terminal",
                    task_state=latest_state,
                )
                yield status_frame(
                    state=latest_state,
                    text=progress_text(progress_message=job.progress_message, percent=job.progress_percent),
                    percent=job.progress_percent,
                    final=True,
                )
                return
            current = _progress_fingerprint(job)
            if current == fingerprint:
                # 没有新信息：发保活帧而不是重复帧 —— 重复帧只会让对端以为自己落后了。
                yield streaming.SSE_HEARTBEAT_FRAME
                continue
            fingerprint = current
            yield status_frame(
                state=latest_state,
                text=progress_text(progress_message=job.progress_message, percent=job.progress_percent),
                percent=job.progress_percent,
                final=False,
            )
        # 循环结束仍未见终态：安全上限（设计 §3.5）。状态取断点时的**真实**映射值，
        # 不谎报成 completed —— 对端据此决定是否再订阅一次。
        # 必须留 warning：30 分钟上限是对规范的有意偏离，审计行只在租户审计页可见，
        # 不落日志就等于「病态任务占住连接半小时」在运维侧完全不可见。只记元数据。
        logger.warning(
            "A2A tasks/resubscribe 触达安全上限，按当前状态收流 (agent_id=%s task_id=%s state=%s max_seconds=%s)",
            agent_id,
            task_id,
            latest_state,
            SUBSCRIPTION_MAX_SECONDS,
        )
        schedule_audit_once(AUDIT_OUTCOME_OK, ended_by="safety-cap", task_state=latest_state)
        yield status_frame(
            state=latest_state,
            text=progress_text(progress_message=latest_job.progress_message, percent=latest_job.progress_percent),
            percent=latest_job.progress_percent,
            final=True,
        )
    except (GeneratorExit, asyncio.CancelledError):
        # 对端断连（``aclose()``）或真实断连（Starlette 取消消费任务）：终态帧不会再发，但留痕
        # 要在这里补上 ——「谁中途掐了连接」正是审计要回答的问题之一。只能同步调度、不能再 yield。
        schedule_audit_once(AUDIT_OUTCOME_CANCELED, ended_by="disconnect", task_state=latest_state)
        raise
    except Exception:
        # 订阅期间的非预期异常（任务在流中途被删、Redis 与 DB 同时不可用）：回一帧 failed 终态
        # 再收流 —— 绝不让对端等到「流突然断掉却没有终态帧」，也不让留痕丢在这条路径上。
        logger.exception("A2A tasks/resubscribe 订阅中断: agent_id=%s task_id=%s", agent_id, task_id)
        schedule_audit_once(AUDIT_OUTCOME_FAILED, ended_by="failed", task_state=TASK_STATE_FAILED)
        yield status_frame(state=TASK_STATE_FAILED, text="订阅中断", percent=None, final=True)
    finally:
        # 内层生成器不随外层关闭自动清理（正常收流时它还挂在 get_message 上，redis 订阅要到 GC
        # 才撤）：显式 aclose 触发它的 finally 取消订阅。已耗尽时是无操作。
        await jobs.aclose()
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd backend && uv run python -m pytest -q tests/tenant/a2a/test_a2a_task_resubscribe.py
```

预期：全绿。若 `test_frames_follow_deduped_task_status_artifact_terminal` 的 `mids` 断言失败，检查「首帧消费后是否已把指纹种下」——种子必须来自首帧那个快照（否则第一个无变化快照会被误发成帧）。

- [ ] **Step 5: 补上「首产出为空闲刻度」的兜底分支测试**

在 `tests/tenant/a2a/test_a2a_task_resubscribe.py` 的「断连与异常」一节末尾追加：

```python
@pytest.mark.asyncio
async def test_first_item_tick_closes_stream_with_failed_audit(monkeypatch, audit_recorder, owned_job):  # noqa: ANN001
    """契约被改坏（首产出竟是空闲刻度）时按失败收尾：不成空流、不变成 500。"""
    monkeypatch.setattr(subscription_svc, "watch_generative_job", _scripted([None]))

    opened = await subscription_svc.open_task_subscription(_Db(agent=_agent()), _ctx(), AGENT_ID, _params(), base_url=BASE)

    assert await _json_frames(opened) == []

    await audit_svc.drain_pending_audits()
    assert audit_recorder[0]["outcome"] == server_mod.AUDIT_OUTCOME_FAILED
    assert audit_recorder[0]["detail"]["endedBy"] == "failed"
```

- [ ] **Step 6: 跑整组测试**

```bash
cd backend && uv run python -m pytest -q tests/tenant/a2a/ tests/tenant/generative/
```

预期：全绿。

- [ ] **Step 7: 提交**

```bash
cd backend && git add packages/miles-portal/src/miles_portal/tenant/a2a/services/subscription.py tests/tenant/a2a/test_a2a_task_resubscribe.py
git commit -F - <<'EOF'
feat(a2a): 实现 tasks/resubscribe 订阅生成任务进度

对端断连后原先只能退化为 tasks/get 轮询，而进度推送能力本就存在。订阅流只发
变化帧、空闲发保活帧；产物只在本次订阅期间产出时用 artifact-update 下发，订阅
时已终态的则直接挂首帧，同一产物不在一条流里出现两次。
EOF
```

---

### Task 5: 视图接线、审计动作登记与 HTTP 面测试

**Files:**
- Modify: `backend/packages/miles-openapi/src/miles_openapi/views/a2a_server.py`
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/audit_log/meta.py:42`
- Modify: `backend/tests/tenant/a2a/test_a2a_audit.py`（两处动作集合）
- Test: `backend/tests/api/test_a2a_server_api.py`
- Modify: `backend/openapi.snapshot.json`（视图 docstring 变更导致快照漂移）

**Interfaces:**
- Consumes: Task 4 的 `open_task_subscription`、Task 1 的 `AUDIT_ACTION_TASKS_RESUBSCRIBE`
- Produces: HTTP 面 `tasks/resubscribe` → `text/event-stream`；审计页可选动作 `A2A 订阅任务更新`

- [ ] **Step 1: 写失败测试**

`backend/tests/api/test_a2a_server_api.py` 追加三个用例（放在 `test_stream_preflight_error_keeps_json_content_type` 之后，与 `message/stream` 那两条对称）：

```python
@pytest.mark.asyncio
async def test_resubscribe_routes_to_sse_stream(as_a2a, api_client, monkeypatch):
    """tasks/resubscribe 与 message/stream 共用端点，按 method 分流为 SSE。"""
    seen: dict = {}

    async def fake_subscribe(_db, _ctx, _agent_id, payload, *, base_url):  # noqa: ANN001
        seen["method"] = payload["method"]
        seen["base_url"] = base_url

        async def frames():  # noqa: ANN202
            yield 'data: {"jsonrpc": "2.0", "id": 1, "result": {"kind": "task"}}\n\n'
            yield ": ping\n\n"
            yield 'data: {"jsonrpc": "2.0", "id": 1, "result": {"kind": "status-update", "final": true}}\n\n'

        return frames()

    monkeypatch.setattr(view_mod, "open_task_subscription", fake_subscribe)

    resp = await api_client.post(
        RPC_PATH,
        json={"jsonrpc": "2.0", "id": 1, "method": "tasks/resubscribe", "params": {"id": str(uuid4())}},
    )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    data_lines = [line for line in resp.text.splitlines() if line.startswith("data: ")]
    assert len(data_lines) == 2
    assert json.loads(data_lines[-1][len("data: ") :])["result"]["final"] is True
    assert seen["method"] == "tasks/resubscribe"
    # 产物下载地址是绝对地址，故服务层需要请求推导出的 base_url
    assert seen["base_url"].startswith("http://test")


@pytest.mark.asyncio
async def test_resubscribe_preflight_error_keeps_json_content_type(as_a2a, api_client, monkeypatch):
    """前置失败（任务不存在 / 不属于该智能体 / 合成 id）不进 SSE，仍回 JSON-RPC 信封。"""

    async def fake_subscribe(*_args, **_kwargs):  # noqa: ANN002, ANN003
        return {"jsonrpc": "2.0", "id": 1, "error": {"code": -32001, "message": "生成任务不存在"}}

    monkeypatch.setattr(view_mod, "open_task_subscription", fake_subscribe)

    resp = await api_client.post(
        RPC_PATH,
        json={"jsonrpc": "2.0", "id": 1, "method": "tasks/resubscribe", "params": {"id": str(uuid4())}},
    )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.json()["error"]["code"] == -32001


@pytest.mark.asyncio
async def test_resubscribe_rate_limited_before_sse(as_a2a, api_client, monkeypatch):
    """订阅可能开 30 分钟，超限更要在开流前拦下（否则 429 无处安放）。"""
    from miles_core.risk.enforce import RateLimitHit

    seen: dict = {}

    async def fake_limit(*_args, **kwargs):  # noqa: ANN002, ANN003
        seen["path"] = kwargs["path"]
        return RateLimitHit(rule_id=uuid4(), limit_per_minute=5, retry_after_seconds=3)

    def fail_subscribe(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("超限时不应进入订阅生成器")

    monkeypatch.setattr(view_mod, "check_a2a_rate_limit", fake_limit)
    monkeypatch.setattr(view_mod, "open_task_subscription", fail_subscribe)

    resp = await api_client.post(
        RPC_PATH,
        json={"jsonrpc": "2.0", "id": 1, "method": "tasks/resubscribe", "params": {"id": str(uuid4())}},
    )

    assert resp.status_code == 429
    assert resp.headers["Retry-After"] == "3"
    assert resp.json()["error"]["code"] == -32000
    assert seen["path"] == RPC_PATH
```

`backend/tests/tenant/a2a/test_a2a_audit.py` 里两处动作集合各加一行（两处都要，否则只改一处会让「命名空间」用例漏检新动作）：

```python
        server_mod.AUDIT_ACTION_TASKS_RESUBSCRIBE,
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && uv run python -m pytest -q tests/api/test_a2a_server_api.py tests/tenant/a2a/test_a2a_audit.py
```

预期：`AttributeError: <module 'miles_openapi.views.a2a_server' ...> has no attribute 'open_task_subscription'` 与审计动作未登记的断言失败。

- [ ] **Step 3: 实现视层分流**

`backend/packages/miles-openapi/src/miles_openapi/views/a2a_server.py`：

3a. import 区：加 `from collections.abc import AsyncIterator`，并在既有 `from miles_portal.tenant.a2a.services.server import (...)` 之后加：

```python
from miles_portal.tenant.a2a.services.subscription import open_task_subscription
```

3b. 在 `a2a_jsonrpc` 之前加一个分流小工具：

```python
def _stream_or_json(opened: dict | AsyncIterator[str]) -> Response:
    """流式入口的两种返回：前置失败回普通 JSON，通过则回 SSE。

    前置失败不能进 SSE —— 响应头一旦写成 ``text/event-stream``，HTTP 状态码与
    ``Retry-After`` 就没处放了，对端只能从半条流里猜。
    """
    if isinstance(opened, dict):
        return JSONResponse(opened)
    return StreamingResponse(opened, media_type="text/event-stream", headers=_SSE_HEADERS)
```

3c. `a2a_jsonrpc` 的 docstring 与分流段改为（`base_url` 提前取，两个流式方法与普通分发都要用）：

```python
    """A2A JSON-RPC 端点（``message/send`` / ``message/stream`` / ``tasks/*``）。

    ``message/stream`` 与 ``tasks/resubscribe`` 按 A2A 约定走 SSE，与其它方法共用同一 URL；
    请求体非 JSON 时回 -32700 信封。前置校验失败的流式请求回普通 JSON，不进入 SSE。

    限流在鉴权之后、分发之前：维度取 API Key 行 id（见 ``services.limits``）。超限回
    HTTP 429 + ``Retry-After``，正文仍是 JSON-RPC 错误信封（``-32000``）—— 外部客户端
    按 JSON-RPC 解析，且只有它能把错误对回自己的 ``id``。流式请求也在这里被拦下，
    避免响应头已写成 ``text/event-stream`` 后无处安放状态码。
    """
    try:
        payload = await request.json()
    except ValueError:
        return JSONResponse(jsonrpc_error(None, PARSE_ERROR, "请求体不是合法 JSON"))
    req_id: object = payload.get("id") if isinstance(payload, dict) else None
    hit = await check_a2a_rate_limit(ctx, agent_id, path=request.url.path, ip=client_ip(request))
    if hit is not None:
        return JSONResponse(
            jsonrpc_error(
                req_id,
                RATE_LIMITED,
                RATE_LIMIT_MESSAGE,
                data={"kind": "rate_limit", "retryAfterSeconds": hit.retry_after_seconds},
            ),
            status_code=429,
            headers={"Retry-After": str(hit.retry_after_seconds)},
        )
    base_url = str(request.base_url)
    method = payload.get("method") if isinstance(payload, dict) else None
    if method == "message/stream":
        return _stream_or_json(await open_a2a_stream(db, ctx, agent_id, payload))
    if method == "tasks/resubscribe":
        return _stream_or_json(await open_task_subscription(db, ctx, agent_id, payload, base_url=base_url))
    return JSONResponse(await handle_a2a_rpc(db, ctx, agent_id, payload, base_url=base_url))
```

- [ ] **Step 4: 登记审计动作**

`backend/packages/miles-portal/src/miles_portal/tenant/audit_log/meta.py`，在 `("a2a.artifact.download", "A2A 下载任务产物", None),` 之后加：

```python
    ("a2a.tasks.resubscribe", "A2A 订阅任务更新", None),
```

- [ ] **Step 5: 跑测试确认通过**

```bash
cd backend && uv run python -m pytest -q tests/api/test_a2a_server_api.py tests/tenant/a2a/
```

预期：全绿。

- [ ] **Step 6: 重写 OpenAPI 快照**

```bash
cd backend && uv run python -m miles_server.scripts.export_openapi --check
```

预期：报漂移（`a2a_jsonrpc` 的 docstring 进了 OpenAPI description）。确认漂移只涉及该路由的描述后重写：

```bash
cd backend && uv run python -m miles_server.scripts.export_openapi --write && git diff --stat openapi.snapshot.json
```

预期：只有 `openapi.snapshot.json` 变更，且 diff 只含 `a2a_jsonrpc` 描述文字。

- [ ] **Step 7: 全后端回归 + 提交**

```bash
cd backend && uv run python -m pytest -q && uv run ruff check . && uv run ruff format --check .
```

预期：全绿、无 lint / 格式问题。

```bash
cd backend && git add packages/miles-openapi/src/miles_openapi/views/a2a_server.py packages/miles-portal/src/miles_portal/tenant/audit_log/meta.py tests/api/test_a2a_server_api.py tests/tenant/a2a/test_a2a_audit.py openapi.snapshot.json
git commit -F - <<'EOF'
feat(a2a): 接线 tasks/resubscribe 并登记审计动作

视图按 method 分流为 SSE，与 message/stream 同法；限流仍在开流之前判出，
订阅可能开半小时，429 更不能等到流开起来才发。审计动作不登记的话，租户在审计页
的下拉里筛不到自己的订阅调用。
EOF
```

---

### Task 6: 文档同步与全量质量门

**Files:**
- Modify: `docs/guides/a2a.md`（第 99 行、方法表、新增订阅语义段、审计表、第 185+ 行待做）
- Modify: `docs/features/a2a-interconnect.md`（第 40 行、第 131 行、流式段）
- Modify: `docs/architecture/technical-design.md:655`
- Modify: `docs/superpowers/specs/2026-09-20-a2a-tasks-resubscribe-design.md`（只改「待做」相关表述，若需要）

**Interfaces:**
- Consumes: Task 1-5 的全部产物
- Produces: 与实现一致的对外文档

- [ ] **Step 1: `docs/guides/a2a.md` 方法表加一行**

在 `tasks/cancel` 那行之后加：

```markdown
| `tasks/resubscribe` | 续播未结束生成任务的进度（SSE）。首帧 `Task`、其后只在状态/进度变化时发 `status-update`，空闲发保活注释帧，终态前补 `artifact-update`。`params.id` 必须是真的生成任务 id |
```

- [ ] **Step 2: 删掉「未实现」表述并补订阅语义段**

2a. 把第 99 行的整句替换为：

```markdown
`tasks/pushNotificationConfig/*` 未实现，回 `-32601`（不静默成功）。
```

2b. 在「**流式语义（`message/stream`）**」那一段之后、「**对端消费方式（重要）**」之前，插入：

```markdown
**订阅语义（`tasks/resubscribe`）：** 用于对端断连后接回未结束的生成任务。`params.id` 只接受
真的生成任务 id（`message/stream` 的合成 `taskId` 不落库，拿它来订阅回 `-32001`）。

帧序列：首帧 `Task`（即当前快照）→ 状态或进度变化时的 `status-update`（`final=false`，
进度文字在 `status.message.parts[].text`、百分比在 `status.message.metadata.percent`）→
任务转入终态时先逐条 `artifact-update`、再一帧 `final=true` 收流。订阅时任务**已**终态则产物
直接挂在首帧上，不发 `artifact-update`。

- **空闲即保活**：没有新状态时下发的也是 `status-update` 之外的 SSE 注释帧 `: ping`，约每 2 秒一次。
- **不回填断连期间的事件**：只发订阅之后的新事件；首帧快照足以让对端对齐当前进度（规范把「是否回填」留给实现自定）。
- **安全上限 30 分钟**：逾期仍未终态则以任务当前**真实状态** + `final=true` 收流（规范要求流在 interrupted/terminal 结束，此处是有意偏离）—— 对端可据此再订阅一次。
- **`contextId` 可能缺失**：规范把 `TaskStatusUpdateEvent.contextId` 标为必填，本平台沿用 `Task.contextId` 的既有口径（解析不到就省略，不塞空串冒充标识），故对端必须容忍无该字段的帧。
- **审计**：`detail.endedBy` 为 `terminal` / `safety-cap` / `disconnect` / `failed`；`detail.taskState` 为收流时的 A2A 状态（任务被取消时是 `canceled`，此时 `outcome` 仍是 `ok` —— `canceled` 这一 outcome 专指对端断连）。
```

- [ ] **Step 3: `docs/guides/a2a.md` 审计表与待做**

3a. 审计动作表加一行：

```markdown
| `a2a.tasks.resubscribe` | `tasks/resubscribe`：终态收流、30 分钟上限、对端断连、前置校验失败各记一次 |
```

3b. 「## 待做」列表首项改为：

```markdown
- `tasks/pushNotificationConfig/*`（现回方法未找到）
```

- [ ] **Step 4: `docs/features/a2a-interconnect.md`**

4a. 第 40 行（「### 1.3 明确不做」首项）改为：

```markdown
- `tasks/pushNotificationConfig/*`（现回方法未找到）
```

4b. 第 40 行上方那句方法清单（`- JSON-RPC 方法：...`）改为：

```markdown
- JSON-RPC 方法：`message/send`、`message/stream`（SSE 真流式）、`tasks/get`、`tasks/cancel`、`tasks/resubscribe`（续播生成任务进度）
```

4c. 第 131 行那句改为：

```markdown
产物下载走鉴权端点（平台不暴露签名 URL），授权限「该智能体 · 该任务 · 该产物」。`tasks/resubscribe` 以真实生成任务 id 续播进度流（首帧 `Task`、变化帧 `status-update`、终态前 `artifact-update`、空闲保活帧、30 分钟安全上限）；`pushNotificationConfig/*` 未实现，回 `-32601`。
```

- [ ] **Step 5: `docs/architecture/technical-design.md`**

第 655 行那句改为：

```markdown
| A2A 对外 Server 流式 | 🔶 | Card（`protocolVersion=0.3`、`streaming=true`）、`message/send`、`message/stream` SSE 流式、`contextId` 多轮、`tasks/get` / `tasks/cancel`、`tasks/resubscribe` 续播、产物下载 ✅；`pushNotificationConfig/*` 待做；见 [a2a.md](../guides/a2a.md) |
```

- [ ] **Step 6: 全量质量门**

```bash
cd backend && uv run python -m pytest -q && uv run ruff check . && uv run ruff format --check .
cd .. && make layers-check && make openapi-check
```

预期：全绿。任何一条红都必须在提交前修掉（不许留「已知失败」）。

- [ ] **Step 7: 确认引用面（守卫测试与文档待做计数）**

```bash
cd backend && uv run python -m pytest -q tests/test_no_unreferenced_modules.py
cd .. && rg -n "tasks/resubscribe" docs/ | rg -v "specs/|plans/"
```

预期：守卫测试通过；文档里只剩「已实现」的表述，不再有「未实现 / 现回 `-32601`」把它算进去。

- [ ] **Step 8: 提交**

```bash
git add docs/guides/a2a.md docs/features/a2a-interconnect.md docs/architecture/technical-design.md
git commit -F - <<'EOF'
docs(a2a): 补 tasks/resubscribe 的订阅语义与偏离说明

订阅流的帧序列、去重与保活、不回填、30 分钟上限、contextId 可能缺失这几点，
对端不读文档就必然误判，故一并写明；三处「待做」清单同步移除本项。
EOF
```

---

## 完成后的验收清单

- [ ] `tasks/resubscribe` 从 `-32601` 变为 SSE 流；合成 `taskId` 仍回 `-32001`
- [ ] 帧序列与设计 §3.2 一致（含「已终态时不发 `artifact-update`」）
- [ ] 保活帧在空闲路径与「快照无变化」路径都能发出
- [ ] 一次调用恰好一条审计流水（终态 / 上限 / 断连 / 前置失败各覆盖）
- [ ] `test_job_stream_events.py` 13 条一字未改仍全绿
- [ ] 五道质量门全绿；`docs/` 无过期的「未实现」表述
