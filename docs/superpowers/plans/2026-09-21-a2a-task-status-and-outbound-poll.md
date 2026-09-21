# A2A 出站任务轮询与 Task 状态准确性 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让出站 A2A Client 认识 `Task` 与 JSON-RPC `error` 两种响应（有限轮询 + 分层判错），并把 Server 侧 `Task.status` 的 `timestamp` 换成真实状态时间、补上进度文案。

**Architecture:** 三块改动都落在「A2A 对外面」的既有边界内。Client 侧在 `invoke_a2a_peer` 的响应处理处串一条**固定顺序**的分类链（`error` → `task` → `text`），`task` 走新增的有限轮询再渲染成产物引用清单；`_extract_text_from_response` 保持不动，只把「成功还是失败」的判断收回调用层。Server 侧把 `status` 的构造抽成 `build_a2a_task_status` 作为单一维护点，`build_a2a_task` 与 `build_a2a_status_update` 共用，再让 5 个调用点中的 3 个改用任务的真实 `updated_at` 与进度。另补一个**不被调用**的出站 `tasks/cancel` 能力。

**Tech Stack:** Python 3.12+ / FastAPI / SQLAlchemy（async）/ httpx / pytest + pytest-asyncio / uv workspace

**Spec:** `docs/superpowers/specs/2026-09-21-a2a-task-status-and-outbound-poll-design.md`

## Global Constraints

- 轮询间隔 `TASK_POLL_INTERVAL_SECONDS = 2.0`，总上限 `TASK_POLL_TIMEOUT_SECONDS = 60.0` —— **模块常量，不新增任何配置项**。
- 停止轮询的状态 = 终态 `{completed, failed, canceled, rejected}` ∪ 中断态 `{input-required, auth-required}`。
- 轮询总时长由 `time.monotonic()` 的 deadline 控制；`httpx` 的 `timeout=60.0` 是**单请求**超时，不得用它当总上限。
- 产物只渲染引用（`artifactId` / `name` / `mimeType` / `uri`），**不下载**、不处理二进制。
- `_extract_text_from_response` 及其特征化测试（`tests/tenant/agents/test_a2a_extract_text.py`）**一字不动**。
- `message/send`（`services/server.py:256`）与 `message/stream` 首帧（`services/server.py:785`）的 `timestamp` **保持 `now_iso()`**。
- 响应分流顺序固定 `error` → `task` → `text`，不得调整。
- `cancel_a2a_peer_task` **不得被任何路径调用**。
- 全部命令在 `backend/` 目录下执行；提交信息用简体中文，格式 `<type>(<scope>): <简述>`。
- 五道质量门收尾必须全过：`uv run python -m pytest -q`、`uv run ruff check .`、`uv run ruff format --check .`、`make layers-check`、`make openapi-check`。

---

## File Structure

| 文件 | 职责 | 本计划中的动作 |
|---|---|---|
| `backend/packages/miles-portal/src/miles_portal/tenant/a2a/server.py` | 纯逻辑：Card 构造、Task/Event 形状、时间戳 | 新增 `build_a2a_task_status` / `timestamp_iso`；`build_a2a_task` 支持 `text`/`percent`；`build_a2a_status_update` 改为共用 |
| `backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/server.py` | A2A Server 用例层：`handle_a2a_rpc` / `tasks/get` / `tasks/cancel` / `message/send` | 3 个 `build_a2a_task` 调用点改接线（其中 1 处不变） |
| `backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/subscription.py` | `tasks/resubscribe` 用例层 | 首帧改用真实时间 + 进度 |
| `backend/packages/miles-portal/src/miles_portal/tenant/a2a/client.py` | 出站 Client：`invoke_a2a_peer` 与响应解析 | 新增 `_jsonrpc_error` / `_looks_like_task` / `_task_state` / `_render_agent_task` / `_artifact_lines` / `_resolve_agent_task` / `_tasks_get_payload` / `cancel_a2a_peer_task`；改造 `invoke_a2a_peer` |
| `backend/tests/tenant/a2a/test_a2a_server_card.py` | Server 纯逻辑单测 | 新增 Task 1 的用例；Task 2 给 `_job` / `cancel_job` 替身补字段 |
| `backend/tests/tenant/a2a/test_a2a_task_resubscribe.py` | resubscribe 单测 | 替身补 `updated_at`；新增首帧进度断言 |
| `backend/tests/api/test_a2a_server_api.py` | A2A HTTP 面集成测试 | 替身补 `updated_at`；新增 `tasks/get` 时间戳与进度断言 |
| `backend/tests/tenant/agents/test_a2a_client_invoke.py` | **新建** 出站调用行为测试 | Task 3/4/5/6 的用例 |
| `docs/guides/a2a.md`、`docs/features/a2a-interconnect.md` | 对外文档 | Task 7 |

---

## Task 1: Server 侧纯函数 —— `build_a2a_task_status` / `timestamp_iso`

**Files:**
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/a2a/server.py:259-321`（`now_iso`、`progress_text`、`build_a2a_task`）
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/a2a/server.py:324-364`（`build_a2a_status_update`）
- Test: `backend/tests/tenant/a2a/test_a2a_server_card.py`

**Interfaces:**
- Consumes: 现有 `now_iso() -> str`（`server.py:259`）、`build_a2a_agent_message(*, text, context_id, task_id=None) -> dict`（`server.py:304`）
- Produces:
  - `build_a2a_task_status(*, state: str, timestamp: str, context_id: str | None = None, text: str | None = None, percent: object = None, message_task_id: str | None = None, job_task_id: str | None = None) -> dict`
  - `timestamp_iso(value: datetime | None) -> str`
  - `build_a2a_task(*, task_id, context_id, state, timestamp, artifacts=None, text=None, percent=None) -> dict`（新增末两个 kw 参数）
  - `build_a2a_status_update(...)` 签名不变

- [ ] **Step 1: 写失败测试**

追加到 `backend/tests/tenant/a2a/test_a2a_server_card.py` 末尾。先确认该文件已 import 的符号，把缺的加进顶部 import 块（现有 import 块在同一处，含 `build_a2a_task`、`build_a2a_status_update`）：

```python
from datetime import UTC, datetime

from miles_portal.tenant.a2a.server import (  # noqa:  (合并进现有 import 块，勿新建)
    build_a2a_status_update,
    build_a2a_task,
    build_a2a_task_status,
    timestamp_iso,
)


def _without_message_id(status: dict) -> dict:
    """剔除每次构造都会新生成的 ``messageId``。

    ``build_a2a_agent_message`` 用 ``uuid4()`` 生成 ``messageId``（消息身份，不是形状），
    两次构造必然不同；要比的是**形状**，不是身份。
    """
    message = status.get("message")
    if not isinstance(message, dict):
        return status
    return {**status, "message": {k: v for k, v in message.items() if k != "messageId"}}


def test_build_a2a_task_status_is_the_single_source_of_shape():
    """Task 与 status-update 的 ``status`` 必须逐键等价 —— 形状只在一处维护。"""
    status_from_task = build_a2a_task(
        task_id="j1",
        context_id="c1",
        state="working",
        timestamp="2026-09-18T00:00:00+00:00",
        text="45% 渲染中",
        percent=45,
    )["status"]
    status_from_update = build_a2a_status_update(
        task_id="j1",
        context_id="c1",
        state="working",
        timestamp="2026-09-18T00:00:00+00:00",
        text="45% 渲染中",
        percent=45,
    )["status"]

    assert _without_message_id(status_from_task) == _without_message_id(status_from_update)


def test_build_a2a_task_omits_status_message_without_text():
    """无进度可说时不附 ``status.message``，也不塞空串。"""
    task = build_a2a_task(task_id="j1", context_id=None, state="working", timestamp="t")

    assert task["status"] == {"state": "working", "timestamp": "t"}


def test_build_a2a_task_status_message_carries_task_id_and_percent():
    task = build_a2a_task(task_id="j1", context_id="c1", state="working", timestamp="t", text="45%", percent=45)

    message = task["status"]["message"]
    assert message["parts"] == [{"kind": "text", "text": "45%"}]
    assert message["taskId"] == "j1"
    assert message["contextId"] == "c1"
    assert message["metadata"] == {"percent": 45}


def test_build_a2a_task_status_omits_percent_metadata_when_absent():
    """``percent`` 为 None 时不写 ``metadata.percent``；无其它 metadata 时整个键都省掉。"""
    task = build_a2a_task(task_id="j1", context_id=None, state="working", timestamp="t", text="渲染中")

    assert "metadata" not in task["status"]["message"]


def test_timestamp_iso_formats_aware_datetime():
    assert timestamp_iso(datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)) == "2026-01-02T03:04:05+00:00"


def test_timestamp_iso_falls_back_to_now_when_absent(monkeypatch):  # noqa: ANN001
    monkeypatch.setattr("miles_portal.tenant.a2a.server.now_iso", lambda: "FIXED")

    assert timestamp_iso(None) == "FIXED"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run python -m pytest tests/tenant/a2a/test_a2a_server_card.py -q -k "task_status or timestamp_iso or status_message"`

Expected: FAIL/ERROR —— `ImportError: cannot import name 'build_a2a_task_status' from 'miles_portal.tenant.a2a.server'`

- [ ] **Step 3: 实现 `build_a2a_task_status` 与 `timestamp_iso`**

在 `server.py` 里 `progress_text` 之后、`build_a2a_task` 之前插入（`now_iso` 在 259，`progress_text` 在 264-276）：

```python
def timestamp_iso(value: datetime | None) -> str:
    """``datetime`` → A2A ``TaskStatus.timestamp``；非 ``datetime`` 回退当前时刻。

    任务的真实状态时间（``TimestampMixin.updated_at``）优先：用请求时刻会让对端每次都看到
    「刚刚更新」，据它判断新鲜度、超时或去重都会误判。``message/stream`` 的合成 taskId 与
    ``message/send`` 的提交快照无真实对象可依，调用点自行传 ``now_iso()``。
    """
    return value.isoformat() if isinstance(value, datetime) else now_iso()


def build_a2a_task_status(
    *,
    state: str,
    timestamp: str,
    context_id: str | None = None,
    text: str | None = None,
    percent: object = None,
    message_task_id: str | None = None,
    job_task_id: str | None = None,
) -> dict:
    """A2A ``TaskStatus``：``Task.status`` 与 ``TaskStatusUpdateEvent.status`` 共用一份形状。

    ``text`` 与 ``percent`` 成对描述进度：``text`` 渲染成嵌套消息的文本 part，``percent``
    写进该消息的 ``metadata.percent``。``text`` 为空则**不附** ``status.message`` —— 与其
    塞一个空串冒充「有进度」，不如让对端明确知道本帧没有进展可说。

    ``job_task_id`` 非空时写入 ``metadata.a2aJobTaskId``：``message/stream`` 的 taskId 是
    合成的（流开始时就得定），生成任务 id 只有跑完才知道，故不强行合一，改用该扩展位串起来。
    """
    status: dict = {"state": state, "timestamp": timestamp}
    if text is None:
        return status
    message = build_a2a_agent_message(text=text, context_id=context_id, task_id=message_task_id)
    metadata: dict = {}
    if job_task_id:
        metadata["a2aJobTaskId"] = job_task_id
    if percent is not None:
        metadata["percent"] = percent
    if metadata:
        message["metadata"] = metadata
    status["message"] = message
    return status
```

- [ ] **Step 4: 改造 `build_a2a_task`**

把 `server.py:279-301` 的 `build_a2a_task` 整体替换为：

```python
def build_a2a_task(
    *,
    task_id: str,
    context_id: str | None,
    state: str,
    timestamp: str,
    artifacts: list[dict] | None = None,
    text: str | None = None,
    percent: object = None,
) -> dict:
    """构造 A2A ``Task``。

    ``contextId`` / ``artifacts`` / ``status.message`` 均为可选：解析不到就省略而非塞空值；
    ``history`` 暂不产出（对端的原始消息本就在请求里）。

    ``text`` / ``percent`` 与 ``build_a2a_status_update`` 同名同义，透传给
    ``build_a2a_task_status`` —— ``status`` 的形状只在那一个函数里维护。
    """
    task: dict = {
        "kind": "task",
        "id": task_id,
        "status": build_a2a_task_status(
            state=state,
            timestamp=timestamp,
            context_id=context_id,
            text=text,
            percent=percent,
            message_task_id=task_id,
        ),
    }
    if context_id:
        task["contextId"] = context_id
    if artifacts:
        task["artifacts"] = artifacts
    return task
```

- [ ] **Step 5: 让 `build_a2a_status_update` 共用同一构造函数**

把 `server.py` 里 `build_a2a_status_update` 开头的这段：

```python
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
```

替换为：

```python
    status = build_a2a_task_status(
        state=state,
        timestamp=timestamp,
        context_id=context_id,
        text=text,
        percent=percent,
        message_task_id=task_id,
        job_task_id=job_task_id,
    )
```

函数体其余部分（`event` 构造、`final`、条件性 `contextId`）保持不变。

- [ ] **Step 6: 运行测试确认通过**

Run: `uv run python -m pytest tests/tenant/a2a/test_a2a_server_card.py -q`

Expected: PASS（新增用例全绿，且该文件既有用例无回归 —— 尤其是 `test_build_a2a_task_shape` 与 `test_build_a2a_task_omits_absent_context_id`）

Run: `uv run python -m pytest tests/tenant/a2a/ -q`

Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add backend/packages/miles-portal/src/miles_portal/tenant/a2a/server.py backend/tests/tenant/a2a/test_a2a_server_card.py
git commit -F - <<'EOF'
refactor(a2a): 抽出 build_a2a_task_status 作为 Task 状态的单一维护点

Task 与 status-update 此前各写一份 status 构造，加 status.message 会漂
成两份。抽成共用纯函数，并新增 timestamp_iso 供调用点把请求时刻换成
任务真实更新时间。
EOF
```

---

## Task 2: Server 侧 3 个调用点改用真实时间与进度

**Files:**
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/server.py:402`（`tasks/get`）、`:435`（`tasks/cancel`）、文件顶部 import 块
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/subscription.py:248`、文件顶部 import 块
- Test: `backend/tests/api/test_a2a_server_api.py`、`backend/tests/tenant/a2a/test_a2a_task_resubscribe.py`、`backend/tests/tenant/a2a/test_a2a_server_card.py`（替身补字段）

**Interfaces:**
- Consumes: Task 1 的 `timestamp_iso(value: datetime | None) -> str`；现有 `progress_text(*, progress_message, percent) -> str | None`
- Produces: 无新符号（纯接线）

**关键前提（务必先做）：** 测试里的 job 替身是 `SimpleNamespace`，**4 处**缺 `updated_at` / `progress_message` / `progress_percent`，接线后会因 `AttributeError` 大面积报错。故 Step 1 先补齐替身字段，再写断言。

- [ ] **Step 1: 先补测试替身的字段（否则接线后大面积 AttributeError）**

接线后 `tasks/get`、`tasks/cancel`、订阅首帧会读 `job.updated_at` / `job.progress_message` / `job.progress_percent`。生产对象是 ORM `GenerativeJob`（`TimestampMixin`）或 `GenerativeJobOut`，三者都有；但测试替身是 `SimpleNamespace`，**共 4 处**缺字段，必须一并补齐（经核对，`git grep updated_at tests/` 当前为 0 处）：

**(1) `backend/tests/tenant/a2a/test_a2a_server_card.py:830` 的 `_job`（缺 3 个字段，影响该文件全部 `tasks/get` 用例）**

```python
def _job(status: str, *, params: dict | None = None, job_id=None, result: dict | None = None, agent_id=None):
    return SimpleNamespace(
        id=job_id or uuid4(),
        status=SimpleNamespace(value=status),
        params=params or {},
        result=result,
        source_ref_type="agent" if agent_id else None,
        source_ref_id=agent_id,
        # 接线后 tasks/get 会读这三个字段：替身补齐，别让缺字段掩盖真实断言
        progress_message=None,
        progress_percent=None,
        updated_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
    )
```

该文件 import 块补 `from datetime import UTC, datetime`。

**(2) `backend/tests/tenant/a2a/test_a2a_server_card.py:941` 的内联 `cancel_job` 返回值（缺 3 个字段；该用例成功走到 `build_a2a_task`）**

```python
        async def cancel_job(self, _job_id):
            return SimpleNamespace(
                id=job_id,
                status=SimpleNamespace(value="cancelled"),
                params={"conversation_id": "c1"},
                # tasks/cancel 的成功路径同样走 build_a2a_task
                progress_message=None,
                progress_percent=None,
                updated_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
            )
```

**(3) `backend/tests/tenant/a2a/test_a2a_task_resubscribe.py:71` 的 `_job`（只缺 `updated_at`）**

```python
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
        updated_at=JOB_UPDATED_AT,
    )
```

在该文件顶部常量区（`JOB_ID` 附近）加：

```python
JOB_UPDATED_AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
```

并把 `from datetime import UTC, datetime` 加进该文件 import 块。

**(4) `backend/tests/api/test_a2a_server_api.py:323` 的 `test_resubscribe_end_to_end_real_service_through_http` 内的局部 `_job`（只缺 `updated_at`）**

`base` 字典补一项：

```python
            source_ref_type="agent",
            source_ref_id=AGENT_ID,
            updated_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
```

并把 `from datetime import UTC, datetime` 加进该文件 import 块。

**无需改动**：`backend/tests/api/test_a2a_server_api.py:592` 那个 `tasks/cancel` 用例的替身（`_Raced.cancel_job` 抛 `NotFoundError`，走不到 `build_a2a_task`），以及 `test_a2a_server_card.py:959` 的 `cancel_job` 抛错替身。

- [ ] **Step 2: 运行全量相关测试确认「加字段」本身不改变行为**

Run: `uv run python -m pytest tests/tenant/a2a/ tests/api/test_a2a_server_api.py -q`

Expected: PASS（替身多一个字段不影响任何断言）

- [ ] **Step 3: 写失败测试 —— `tasks/get` 用真实时间并带进度**

追加到 `backend/tests/api/test_a2a_server_api.py` 末尾（沿用该文件既有模式：`as_a2a` + `api_client` + patch `a2a_svc.get_generative_job_for_tenant` 与 `a2a_svc.write_a2a_audit`）：

```python
@pytest.mark.asyncio
async def test_tasks_get_reports_true_status_time_and_progress(as_a2a, api_client, monkeypatch):
    """``status.timestamp`` 必须是任务真实更新时间，``status.message`` 必须带进度。

    用请求时刻会让对端每次查询都看到「刚刚更新」；而缺 ``status.message`` 会让对端轮询
    时读不到任何进展（订阅流却读得到）。
    """
    job_id = uuid4()
    updated_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)

    agent = Agent()
    agent.id = AGENT_ID
    agent.agent_type = AgentType.CUSTOM
    agent.status = AgentStatus.ENABLED
    agent.config = {A2A_PUBLISH_FLAG: True}
    agent.deleted_at = None

    class _Db:
        async def get(self, _model, _id):  # noqa: ANN001
            return agent

        async def commit(self):  # noqa: ANN201
            pass

    async def override_db():  # noqa: ANN202
        yield _Db()

    job = SimpleNamespace(
        id=job_id,
        tenant_id=uuid4(),
        status=SimpleNamespace(value="running"),
        progress_message="45% 渲染中",
        progress_percent=45,
        result=None,
        params={},
        source_ref_type="agent",
        source_ref_id=AGENT_ID,
        updated_at=updated_at,
    )

    async def _get(_db, _ctx, _job_id):  # noqa: ANN001
        return job

    async def _write(**_kwargs):  # noqa: ANN003
        return None

    as_a2a.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(a2a_svc, "get_generative_job_for_tenant", _get)
    monkeypatch.setattr(a2a_svc, "write_a2a_audit", _write)

    resp = await api_client.post(RPC_PATH, json={"jsonrpc": "2.0", "id": 1, "method": "tasks/get", "params": {"id": str(job_id)}})

    assert resp.status_code == 200
    status = resp.json()["result"]["status"]
    assert status["state"] == "working"
    # 精确等值：这是「不是 now_iso()」唯一有判别力的断言（now_iso() 也是合法 ISO 串）
    assert status["timestamp"] == updated_at.isoformat()
    assert status["message"]["parts"] == [{"kind": "text", "text": "45% 渲染中"}]
    assert status["message"]["metadata"] == {"percent": 45}
```

同一文件新增一条「无进度时不得凭空造 `status.message`」的用例：

```python
@pytest.mark.asyncio
async def test_tasks_get_omits_status_message_without_progress(as_a2a, api_client, monkeypatch):
    """任务没进度可说时，``status.message`` 必须缺席 —— 不塞空串冒充进展。"""
    job_id = uuid4()

    agent = Agent()
    agent.id = AGENT_ID
    agent.agent_type = AgentType.CUSTOM
    agent.status = AgentStatus.ENABLED
    agent.config = {A2A_PUBLISH_FLAG: True}
    agent.deleted_at = None

    class _Db:
        async def get(self, _model, _id):  # noqa: ANN001
            return agent

        async def commit(self):  # noqa: ANN201
            pass

    async def override_db():  # noqa: ANN202
        yield _Db()

    job = SimpleNamespace(
        id=job_id,
        tenant_id=uuid4(),
        status=SimpleNamespace(value="pending"),
        progress_message=None,
        progress_percent=None,
        result=None,
        params={},
        source_ref_type="agent",
        source_ref_id=AGENT_ID,
        updated_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
    )

    async def _get(_db, _ctx, _job_id):  # noqa: ANN001
        return job

    async def _write(**_kwargs):  # noqa: ANN003
        return None

    as_a2a.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(a2a_svc, "get_generative_job_for_tenant", _get)
    monkeypatch.setattr(a2a_svc, "write_a2a_audit", _write)

    resp = await api_client.post(RPC_PATH, json={"jsonrpc": "2.0", "id": 1, "method": "tasks/get", "params": {"id": str(job_id)}})

    assert resp.status_code == 200
    assert set(resp.json()["result"]["status"]) == {"state", "timestamp"}
```

再追加一条 resubscribe 首帧带进度的单测到 `backend/tests/tenant/a2a/test_a2a_task_resubscribe.py`（驱动方式与既有 `test_progress_frame_carries_percent_in_message_metadata` 完全一致：`_scripted` + `open_task_subscription` + `_json_frames`）：

```python
@pytest.mark.asyncio
async def test_first_frame_carries_progress_and_true_time(monkeypatch, owned_job):  # noqa: ANN001
    """订阅首帧就要给出订阅时刻的进度，且时间戳取任务真实更新时间。

    首帧缺进度会让对端在订阅后的第一段静默里什么都看不到；时间戳若用请求时刻，对端每次
    重连都看到「刚刚更新」，据此判断新鲜度会误判。
    """
    job = owned_job(_job("running", progress_message="45% 渲染中", progress_percent=45))
    monkeypatch.setattr(
        subscription_svc,
        "watch_generative_job",
        _scripted([job, _job("running", progress_message="45% 渲染中", progress_percent=45)]),
    )

    opened = await subscription_svc.open_task_subscription(_Db(agent=_agent()), _ctx(), AGENT_ID, _params(), base_url=BASE)
    results = [f["result"] for f in await _json_frames(opened)]

    assert results[0]["kind"] == "task"
    assert results[0]["status"]["timestamp"] == JOB_UPDATED_AT.isoformat()
    assert results[0]["status"]["message"]["parts"][0]["text"] == "45% 渲染中"
    assert results[0]["status"]["message"]["metadata"] == {"percent": 45}
```

> 该用例末尾**不**断言帧数：脚本第二项与首帧进度相同，指纹去重会把它换成保活注释帧。若想同时锁住去重，复用既有 `test_frames_follow_deduped_task_status_artifact_terminal`，不必在此重复。

- [ ] **Step 4: 运行测试确认失败**

Run: `uv run python -m pytest tests/api/test_a2a_server_api.py -q -k "true_status_time or omits_status_message" tests/tenant/a2a/test_a2a_task_resubscribe.py -q`

Expected: FAIL —— `assert '2026-09-21T...' == '2026-01-02T03:04:05+00:00'`（时间戳仍是请求时刻），以及 `KeyError: 'message'`（无进度）

- [ ] **Step 5: 接线 `tasks/get`**

`services/server.py` 顶部 `from miles_portal.tenant.a2a.server import (...)` 块补**两个**符号（经核对，该模块当前既没有 `progress_text` 也没有 `timestamp_iso`；它已 import 了 `now_iso`、`build_a2a_task`、`build_a2a_artifacts`、`to_a2a_task_state`）：

```python
    now_iso,
    progress_text,
    timestamp_iso,
    to_a2a_task_state,
```

然后把 `:402` 的调用改为：

```python
    return jsonrpc_result(
        req_id,
        build_a2a_task(
            task_id=str(job.id),
            context_id=context_id_from_job_params(job.params),
            state=to_a2a_task_state(job.status.value),
            timestamp=timestamp_iso(job.updated_at),
            artifacts=build_a2a_artifacts(job_result=job.result, agent_id=agent_id, task_id=job.id, base_url=base_url),
            text=progress_text(progress_message=job.progress_message, percent=job.progress_percent),
            percent=job.progress_percent,
        ),
    )
```

- [ ] **Step 6: 接线 `tasks/cancel`**

同一文件的 `:435` 改为（`job` 此处是 `cancel_job` 返回的 `GenerativeJobOut`，同样带 `updated_at` / `progress_message` / `progress_percent`）：

```python
    return jsonrpc_result(
        req_id,
        build_a2a_task(
            task_id=str(job.id),
            context_id=context_id_from_job_params(job.params),
            state=to_a2a_task_state(job.status.value),
            timestamp=timestamp_iso(job.updated_at),
            text=progress_text(progress_message=job.progress_message, percent=job.progress_percent),
            percent=job.progress_percent,
        ),
    )
```

- [ ] **Step 7: 接线 `subscription.py` 首帧**

`subscription.py` 顶部 import 块加 `timestamp_iso`（`progress_text` 该文件**已经** import 并在既有 `status_frame` 调用里使用，无需重复添加）。首帧 `:248` 的调用改为（`artifacts=` 一段原样保留，它负责「订阅时已终态则产物挂首帧」）：

```python
                build_a2a_task(
                    task_id=task_id,
                    context_id=context_id,
                    state=latest_state,
                    timestamp=timestamp_iso(first.updated_at),
                    # 订阅时已终态：产物直接挂首帧（一帧讲完整段故事）；否则本次订阅期间产出的
                    # 走 artifact-update 帧，同一产物不在一条流里出现两次。
                    artifacts=(
                        build_a2a_artifacts(job_result=first.result, agent_id=agent_id, task_id=job_id, base_url=base_url) if terminal_at_subscribe else None
                    ),
                    text=progress_text(progress_message=first.progress_message, percent=first.progress_percent),
                    percent=first.progress_percent,
                ),
```

- [ ] **Step 8: 确认 `message/send` 与 `message/stream` 首帧未被改动**

Run: `git diff backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/server.py`

Expected: 只有 `tasks/get` 与 `tasks/cancel` 两处调用点变化；`:256`（`message/send`）与 `:785`（`message/stream` 首帧）**仍为 `timestamp=now_iso()`**，且无 `text`/`percent` 参数。

- [ ] **Step 9: 运行测试确认通过**

Run: `uv run python -m pytest tests/tenant/a2a/ tests/api/test_a2a_server_api.py tests/api/ -q`

Expected: **PASS，不需要修改任何既有断言**。已逐条核对过首帧新增 `status.message` 会不会打脸既有用例，结论是都不会：

| 既有用例 | 为何不受影响 |
|---|---|
| `test_frames_follow_deduped_task_status_artifact_terminal` | `results[0]` 只断言 `kind` / `status.state` / `contextId` / 无 `artifacts`，均与 `status.message` 正交；`mids = results[1:-2]` 仍只有 `"60%"`（首帧的 `"10%"` 与新 `status.message` 都不进 `mids`，且指纹去重逻辑未变） |
| `test_progress_frame_carries_percent_in_message_metadata` | 断言的是 `results[1]`（45%→46% 的变化帧），不是 `results[0]` |
| `test_already_terminal_subscription_puts_artifacts_in_first_frame` | 断言 `[r["kind"] ...] == ["task", "status-update"]` 与 `artifacts`，与 `status.message` 正交 |
| `test_omits_context_id_when_unresolvable` | 该 job 的 `context_id` 解析不到，`build_a2a_agent_message(context_id=None)` 不塞 `contextId`，故 `"contextId" not in frame["status"].get("message", {})` 仍成立 |

若真出现红灯，**先读断言再改代码**：只有断言了「首帧不该有 progress」才说明设计与此前契约冲突，此时停下回报，不要为了让测试变绿而回退实现。

- [ ] **Step 10: 提交**

```bash
git add backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/ backend/tests/
git commit -F - <<'EOF'
fix(a2a): tasks/get 与订阅首帧改用真实状态时间并补进度

5 个 build_a2a_task 调用点此前一律传请求时刻，对端每次查询都看到「刚刚
更新」，据此判断新鲜度会误判；同时不产出 status.message，与订阅流每帧
都带进度的形状不一致，轮询路径读不到任何进展。

message/send 与 message/stream 首帧保持请求时刻：前者上游只给
id/kind/status，后者是合成 taskId，都无真实对象可依。
EOF
```

---

## Task 3: Client 侧 `_jsonrpc_error` 与 error 分流

**Files:**
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/a2a/client.py`（`_extract_text_from_response` 之前新增 helper；`invoke_a2a_peer` 循环内接线）
- Test: `backend/tests/tenant/agents/test_a2a_client_invoke.py`（**新建**）

**Interfaces:**
- Consumes: 现有 `invoke_a2a_peer(peer: A2aPeer, task: str) -> str`、`build_auth_headers`、`_pick_rpc_url`
- Produces:
  - `_jsonrpc_error(data: object) -> tuple[object, str] | None`
  - `invoke_a2a_peer` 在收到 JSON-RPC `error` 时抛 `BadRequestError`

- [ ] **Step 1: 写失败测试（含可复用的 fake）**

新建 `backend/tests/tenant/agents/test_a2a_client_invoke.py`：

```python
"""A2A 出站调用的响应分类：``error`` / ``Task`` / ``Message``。

``invoke_a2a_peer`` 此前把「这次调用成功还是失败」交给 ``_extract_text_from_response``
（一个尽可能榨出文本的宽容函数）决定，于是对端的 JSON-RPC ``error`` 会被当作它的
「回答」写进主模型素材。本文件锁定修正后的分类链。
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from miles_portal.tenant.a2a import client as client_mod


class _Resp:
    def __init__(self, data: dict, status_code: int = 200) -> None:
        self._data = data
        self.status_code = status_code

    def json(self) -> dict:  # noqa: D102
        return self._data


class _SeqClient:
    """按调用顺序返回响应的 httpx.AsyncClient 替身；响应耗尽后重复末项。

    重复末项让「一直 working 直到超时」这类用例不必预先生成几十个响应。
    """

    def __init__(self, responses: list[dict], captured: list[dict]) -> None:
        self._responses = list(responses)
        self._captured = captured

    async def __aenter__(self) -> _SeqClient:
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False

    async def post(self, url: str, *, json: dict | None = None, headers: dict | None = None) -> _Resp:
        self._captured.append({"url": url, "body": json})
        index = min(len(self._captured) - 1, len(self._responses) - 1)
        return _Resp(self._responses[index])


def _patch(monkeypatch, responses: list[dict]) -> list[dict]:  # noqa: ANN001
    captured: list[dict] = []
    monkeypatch.setattr(
        client_mod.httpx,
        "AsyncClient",
        lambda **_kwargs: _SeqClient(responses, captured),
    )
    return captured


def _peer() -> SimpleNamespace:
    return SimpleNamespace(
        name="Peer",
        status=SimpleNamespace(value="active"),
        agent_card_json={"additionalInterfaces": [{"url": "https://peer.example.com/a2a", "transport": "JSONRPC"}]},
        base_url="https://peer.example.com",
        agent_card_url="https://peer.example.com/.well-known/agent-card.json",
        card_display_name="Peer",
        auth_config=None,
    )


def _task(state: str, *, task_id: str = "j1", artifacts=None, progress: str | None = None, percent: int | None = None) -> dict:
    status: dict = {"state": state, "timestamp": "2026-01-02T03:04:05+00:00"}
    if progress is not None:
        status["message"] = {"kind": "message", "role": "agent", "messageId": "m1", "parts": [{"kind": "text", "text": progress}]}
        if percent is not None:
            status["message"]["metadata"] = {"percent": percent}
    body: dict = {"kind": "task", "id": task_id, "status": status}
    if artifacts is not None:
        body["artifacts"] = artifacts
    return body


@pytest.mark.asyncio
async def test_jsonrpc_error_raises_instead_of_masquerading_as_answer(monkeypatch):  # noqa: ANN001
    """对端协议级错误必须抛错，而不是变成「它回答了这句话」。"""
    captured = _patch(monkeypatch, [{"jsonrpc": "2.0", "id": "1", "error": {"code": -32602, "message": "参数错误"}}])

    with pytest.raises(BadRequestError) as excinfo:
        await client_mod.invoke_a2a_peer(_peer(), "你好")

    assert "-32602" in str(excinfo.value)
    assert "参数错误" in str(excinfo.value)
    # 收到结构正确的 JSON-RPC error 说明 endpoint 形态已匹配：不得再探测第二个
    assert len(captured) == 1
```

import 块需要 `from miles_common.exceptions import BadRequestError`。

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run python -m pytest tests/tenant/agents/test_a2a_client_invoke.py -q`

Expected: FAIL —— `Failed: DID NOT RAISE`（当前实现把「参数错误」当回答返回）

- [ ] **Step 3: 实现 `_jsonrpc_error`**

在 `client.py` 的 `_extract_text_from_response` 之前（约 `:153`）插入：

```python
def _jsonrpc_error(data: object) -> tuple[object, str] | None:
    """顶层 ``error`` → ``(code, message)``；无 ``error`` 返回 ``None``。

    JSON-RPC 里 ``error`` 与 ``result`` 互斥，故本函数是「本次调用成功还是失败」的判据。
    此前这个判断被交给 ``_extract_text_from_response``（它刻意让 error 优先于 result 并
    把消息榨成文本，见其特征化测试），结果是协议级失败被当成对端的「回答」写进主模型素材。
    """
    if not isinstance(data, dict) or "error" not in data:
        return None
    err = data["error"]
    if isinstance(err, dict):
        return err.get("code"), str(err.get("message") or err)
    return None, str(err)
```

- [ ] **Step 4: 在 `invoke_a2a_peer` 里接线**

把 `client.py:206-210` 这段：

```python
                data = resp.json()
                text = _extract_text_from_response(data)
                if text:
                    return text
```

替换为：

```python
                data = resp.json()
                # 顺序固定 error → task → text（三者互斥）。判断「成功还是失败」是本层的
                # 职责，不交给榨文本函数：否则对端错误会被当成回答交上去。
                err = _jsonrpc_error(data)
                if err is not None:
                    # 对端已按 JSON-RPC 应答，说明 endpoint 形态已匹配：不再探测下一个，
                    # 直接抛。HTTP ≥ 400 仍走上面的 ``continue`` —— 那可能只是路径不对。
                    raise BadRequestError(f"调用外部 A2A Agent「{peer.name}」失败：对端返回错误 {err[0]} {err[1]}")
                text = _extract_text_from_response(data)
                if text:
                    return text
```

**注意**：`raise BadRequestError` 位于 `try` 内是安全的 —— 该 `try` 的 `except` 子句只捕 `httpx.RequestError` 与 `ValueError`。若后续有人放宽该子句，必须重新审视本行。

- [ ] **Step 5: 运行测试确认通过**

Run: `uv run python -m pytest tests/tenant/agents/test_a2a_client_invoke.py tests/tenant/agents/test_a2a_client_auth.py tests/tenant/agents/test_a2a_extract_text.py -q`

Expected: PASS。`test_a2a_extract_text.py` **必须一条都不改**。

- [ ] **Step 6: 提交**

```bash
git add backend/packages/miles-portal/src/miles_portal/tenant/a2a/client.py backend/tests/tenant/agents/test_a2a_client_invoke.py
git commit -F - <<'EOF'
fix(a2a): 出站把对端 JSON-RPC 错误当失败而非回答

_extract_text_from_response 刻意让 error 优先于 result（有特征化测试
锁定），于是 invoke_a2a_peer 把对端的错误消息当成功回答返回，经
invoke.py 记为 a2a_peer 并进入主模型素材。协议级错误是 A2A 的标准失败
形态，对端任何参数错误都会被读成「它回答了这句话」。

改为在 invoke 层先判顶层 error 即抛 BadRequestError（经 invoke.py 记为
a2a_error）；该 helper 与其特征化测试一字不动。
EOF
```

---

## Task 4: Client 侧 Task 判据与渲染（纯函数）

**Files:**
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/a2a/client.py`
- Test: `backend/tests/tenant/agents/test_a2a_client_invoke.py`

**Interfaces:**
- Consumes: 现有 `_first_part_text(value) -> str | None`
- Produces:
  - `_task_state(task: dict) -> str | None`
  - `_looks_like_task(data: object) -> bool`
  - `_artifact_lines(artifacts: object) -> list[str]`
  - `_render_agent_task(task: dict, *, note: str | None = None) -> str`
  - 常量 `TERMINAL_TASK_STATES` / `INTERRUPTED_TASK_STATES` / `STOP_POLLING_TASK_STATES`

- [ ] **Step 1: 写失败测试**

追加到 `backend/tests/tenant/agents/test_a2a_client_invoke.py`：

```python
def _artifact(name: str | None = "image-1", mime: str | None = "image/png", uri: str | None = "https://peer.example.com/dl/a1") -> dict:
    file: dict = {}
    if name is not None:
        file["name"] = name
    if mime is not None:
        file["mimeType"] = mime
    if uri is not None:
        file["uri"] = uri
    return {"artifactId": "att-1", "parts": [{"kind": "file", "file": file}]}


def test_task_state_reads_nested_state():
    assert client_mod._task_state({"status": {"state": "working"}}) == "working"
    assert client_mod._task_state({"status": {}}) is None
    assert client_mod._task_state({"status": "not-a-dict"}) is None
    assert client_mod._task_state({}) is None


def test_looks_like_task_uses_structure_not_kind():
    """老 peer 不一定带 ``kind``，判据必须落在 ``status.state`` 上。"""
    assert client_mod._looks_like_task({"result": {"status": {"state": "working"}}}) is True
    assert client_mod._looks_like_task({"result": {"kind": "task"}}) is False
    assert client_mod._looks_like_task({"result": {"text": "hi"}}) is False
    assert client_mod._looks_like_task("plain") is False


def test_render_completed_task_lists_artifact_refs():
    out = client_mod._render_agent_task(_task("completed", artifacts=[_artifact()]))

    assert out.splitlines()[0] == "外部任务已完成"
    assert "image-1" in out and "image/png" in out
    assert "https://peer.example.com/dl/a1" in out
    assert "任务 ID：j1" in out


def test_render_artifact_without_uri_is_marked():
    out = client_mod._render_agent_task(_task("completed", artifacts=[_artifact(uri=None)]))

    assert "无下载地址" in out


def test_render_uses_artifact_id_when_name_absent():
    out = client_mod._render_agent_task(_task("completed", artifacts=[_artifact(name=None)]))

    assert "att-1" in out


def test_render_failed_task_shows_progress_text():
    out = client_mod._render_agent_task(_task("failed", progress="模型拒绝生成"))

    assert out.splitlines()[0] == "外部任务失败"
    assert "进展：模型拒绝生成" in out


@pytest.mark.parametrize(
    ("state", "headline"),
    [
        ("canceled", "外部任务已取消"),
        ("rejected", "外部任务被拒绝"),
        ("input-required", "外部任务需要补充输入"),
        ("auth-required", "外部任务需要鉴权"),
        ("working", "外部任务仍在进行（状态：working）"),
        ("unknown", "外部任务状态未知（状态：unknown）"),
    ],
)
def test_render_headline_by_state(state, headline):  # noqa: ANN001
    assert client_mod._render_agent_task(_task(state)).splitlines()[0] == headline


def test_render_appends_note_when_present():
    out = client_mod._render_agent_task(_task("working"), note="已等待 60 秒")

    assert out.splitlines()[-1] == "已等待 60 秒"


def test_stop_polling_states_cover_terminal_and_interrupted():
    """中断态必须停止轮询：对端在等我们补输入/凭证，继续轮询只会白等。"""
    assert client_mod.STOP_POLLING_TASK_STATES == client_mod.TERMINAL_TASK_STATES | client_mod.INTERRUPTED_TASK_STATES
    assert "input-required" in client_mod.STOP_POLLING_TASK_STATES
    assert "auth-required" in client_mod.STOP_POLLING_TASK_STATES
    assert "working" not in client_mod.STOP_POLLING_TASK_STATES
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run python -m pytest tests/tenant/agents/test_a2a_client_invoke.py -q`

Expected: FAIL —— `AttributeError: module ... has no attribute '_task_state'`

- [ ] **Step 3: 实现判据、常量与渲染**

在 `client.py` 的 `_text_from_result_payload` 之后、`_extract_text_from_response` 之前插入。`_jsonrpc_error`（Task 3）已在该位置，把它排在前面，新代码紧跟其后：

```python
#: 终态：任务不再推进，且已有最终结果。
TERMINAL_TASK_STATES = frozenset({"completed", "failed", "canceled", "rejected"})
#: 中断态：规范里 ``input-required`` / ``auth-required`` 同样「不再自行推进」——对端在等
#: 我们补输入或凭证。继续轮询只会白等，应停止并如实回报（尤其是 ``input-required``：
#: 对端的提问通常就写在 ``status.message`` 里，正是我们该带回给上层的东西）。
INTERRUPTED_TASK_STATES = frozenset({"input-required", "auth-required"})
#: 停止轮询的状态集。
STOP_POLLING_TASK_STATES = TERMINAL_TASK_STATES | INTERRUPTED_TASK_STATES

#: 任务状态 → 回答首行。未列出的（含缺失）按「仍在进行 / 状态未知」处理。
_TASK_HEADLINES = {
    "completed": "外部任务已完成",
    "failed": "外部任务失败",
    "canceled": "外部任务已取消",
    "rejected": "外部任务被拒绝",
    "input-required": "外部任务需要补充输入",
    "auth-required": "外部任务需要鉴权",
}


def _task_state(task: dict) -> str | None:
    """``Task.status.state``；缺失或非字符串返回 ``None``。"""
    status = task.get("status")
    if not isinstance(status, dict):
        return None
    state = status.get("state")
    return state if isinstance(state, str) else None


def _looks_like_task(data: object) -> bool:
    """JSON-RPC 响应是否是一个 ``Task``。

    用 ``status.state`` 判定而非 ``kind``：0.3 规范里 ``Task.kind`` 是必填，但本模块一直
    兼容不带 ``kind`` 的松散形状，判据不能建立在它上面。
    """
    if not isinstance(data, dict):
        return False
    result = data.get("result")
    return isinstance(result, dict) and _task_state(result) is not None


def _artifact_lines(artifacts: object) -> list[str]:
    """``Task.artifacts`` → 逐条可读引用（只给地址，绝不下载内容）。"""
    if not isinstance(artifacts, list):
        return []
    lines: list[str] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        label = str(artifact.get("artifactId") or "产物")
        parts = artifact.get("parts")
        file_obj: dict | None = None
        if isinstance(parts, list):
            for part in parts:
                if isinstance(part, dict) and isinstance(part.get("file"), dict):
                    file_obj = part["file"]
                    break
        if file_obj is None:
            lines.append(f"- {label}（无下载地址）")
            continue
        name = file_obj.get("name") or label
        mime = file_obj.get("mimeType")
        suffix = f"（{mime}）" if isinstance(mime, str) and mime else ""
        lines.append(f"- {name}{suffix}：{file_obj.get('uri')}")
    return lines


def _render_agent_task(task: dict, *, note: str | None = None) -> str:
    """``Task`` → 给上层（与主模型）读的多行文本。

    不带 peer 名：调用方 ``invoke.py`` 已用 ``【外部 A2A · {name}】`` 包过，重复无益。
    """
    state = _task_state(task) or "unknown"
    lines = [_TASK_HEADLINES.get(state, f"外部任务仍在进行（状态：{state}）")]
    if state == "unknown":
        lines[0] = "外部任务状态未知（状态：unknown）"
    status = task.get("status")
    message = status.get("message") if isinstance(status, dict) else None
    progress = _first_part_text(message.get("parts")) if isinstance(message, dict) else None
    if progress:
        lines.append(f"进展：{progress}")
    artifacts = task.get("artifacts")
    artifact_lines = _artifact_lines(artifacts)
    if artifact_lines:
        lines.append(f"产物（{len(artifact_lines)} 个）：")
        lines.extend(artifact_lines)
    the_id = task.get("id")
    if isinstance(the_id, str) and the_id:
        lines.append(f"任务 ID：{the_id}")
    if note:
        lines.append(note)
    return "\n".join(lines)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run python -m pytest tests/tenant/agents/test_a2a_client_invoke.py -q`

Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/packages/miles-portal/src/miles_portal/tenant/a2a/client.py backend/tests/tenant/agents/test_a2a_client_invoke.py
git commit -F - <<'EOF'
feat(a2a): 出站 Task 的判据、停止轮询状态与渲染

为「把 Task 当成回答」的修正打底：结构判据（status.state，不依赖
kind）、终态与中断态的停止轮询集合、以及把 Task 渲染成「首行状态 +
进度 + 产物引用 + taskId」的多行文本。产物只给地址，不下载内容。
EOF
```

---

## Task 5: Client 侧有限轮询与接线

**Files:**
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/a2a/client.py`
- Test: `backend/tests/tenant/agents/test_a2a_client_invoke.py`

**Interfaces:**
- Consumes: Task 3 的 `_jsonrpc_error`；Task 4 的 `_looks_like_task` / `_task_state` / `_render_agent_task` / `STOP_POLLING_TASK_STATES`
- Produces:
  - 常量 `TASK_POLL_INTERVAL_SECONDS = 2.0`、`TASK_POLL_TIMEOUT_SECONDS = 60.0`
  - `_tasks_get_payload(task_id: str) -> dict`
  - `async _resolve_agent_task(client, url: str, task: dict, headers: dict[str, str]) -> str`
  - `invoke_a2a_peer` 在 Task 分支上返回轮询结果

- [ ] **Step 1: 写失败测试**

追加到 `backend/tests/tenant/agents/test_a2a_client_invoke.py`：

```python
def _fast_poll(monkeypatch) -> None:  # noqa: ANN001
    """把轮询压到亚毫秒级：测试不该真的睡 60 秒。

    ``_resolve_agent_task`` 在运行时读模块常量，故 monkeypatch 生效。
    """
    monkeypatch.setattr(client_mod, "TASK_POLL_INTERVAL_SECONDS", 0.001)
    monkeypatch.setattr(client_mod, "TASK_POLL_TIMEOUT_SECONDS", 0.02)


@pytest.mark.asyncio
async def test_terminal_task_is_not_polled(monkeypatch):  # noqa: ANN001
    """对端可能同步就绪：已是终态时一次多余请求都不发。"""
    captured = _patch(monkeypatch, [{"jsonrpc": "2.0", "id": "1", "result": _task("completed", artifacts=[_artifact()])}])
    monkeypatch.setattr(client_mod, "TASK_POLL_INTERVAL_SECONDS", 2.0)

    answer = await client_mod.invoke_a2a_peer(_peer(), "生成一张图")

    assert "外部任务已完成" in answer
    assert len(captured) == 1


@pytest.mark.asyncio
async def test_polls_until_completed_and_reports_artifacts(monkeypatch):  # noqa: ANN001
    _fast_poll(monkeypatch)
    captured = _patch(
        monkeypatch,
        [
            {"jsonrpc": "2.0", "id": "1", "result": _task("working")},
            {"jsonrpc": "2.0", "id": "2", "result": _task("working", progress="45% 渲染中", percent=45)},
            {"jsonrpc": "2.0", "id": "3", "result": _task("completed", artifacts=[_artifact(name="封面", mime="image/png")])},
        ],
    )

    answer = await client_mod.invoke_a2a_peer(_peer(), "生成一张图")

    assert "外部任务已完成" in answer
    assert "封面" in answer and "image/png" in answer
    # 首次 message/send + 两次 tasks/get
    assert len(captured) == 3
    assert captured[1]["body"]["method"] == "tasks/get"
    assert captured[1]["body"]["params"] == {"id": "j1"}


@pytest.mark.asyncio
async def test_polls_with_symmetric_endpoint(monkeypatch):  # noqa: ANN001
    """``message/send`` 探到哪个形态，``tasks/get`` 就打对应的那一个。"""
    _fast_poll(monkeypatch)
    captured = _patch(
        monkeypatch,
        [
            {"jsonrpc": "2.0", "id": "1", "result": _task("working")},
            {"jsonrpc": "2.0", "id": "2", "result": _task("completed")},
        ],
    )

    await client_mod.invoke_a2a_peer(_peer(), "生成一张图")

    assert captured[0]["url"] == "https://peer.example.com/a2a/message/send"
    assert captured[1]["url"] == "https://peer.example.com/a2a/tasks/get"


@pytest.mark.asyncio
async def test_timeout_returns_snapshot_with_task_id(monkeypatch):  # noqa: ANN001
    _fast_poll(monkeypatch)
    _patch(monkeypatch, [{"jsonrpc": "2.0", "id": "1", "result": _task("working", progress="45% 渲染中")}])

    answer = await client_mod.invoke_a2a_peer(_peer(), "生成一张图")

    assert answer.splitlines()[0] == "外部任务仍在进行（状态：working）"
    assert "任务 ID：j1" in answer
    assert "已等待" in answer


@pytest.mark.asyncio
async def test_input_required_stops_polling(monkeypatch):  # noqa: ANN001
    """中断态不再轮询：对端在等我们补输入，白等到超时毫无意义。"""
    _fast_poll(monkeypatch)
    captured = _patch(
        monkeypatch,
        [
            {"jsonrpc": "2.0", "id": "1", "result": _task("working")},
            {"jsonrpc": "2.0", "id": "2", "result": _task("input-required", progress="请补充视频时长")},
        ],
    )

    answer = await client_mod.invoke_a2a_peer(_peer(), "生成一段视频")

    assert answer.splitlines()[0] == "外部任务需要补充输入"
    assert "请补充视频时长" in answer
    assert len(captured) == 2


@pytest.mark.asyncio
async def test_poll_jsonrpc_error_falls_back_to_snapshot(monkeypatch):  # noqa: ANN001
    """对端不支持 tasks/get（``-32601``）时回退到最后一次已知状态，而不是抛给上层。"""
    _fast_poll(monkeypatch)
    _patch(
        monkeypatch,
        [
            {"jsonrpc": "2.0", "id": "1", "result": _task("working")},
            {"jsonrpc": "2.0", "id": "2", "error": {"code": -32601, "message": "不支持的方法"}},
        ],
    )

    answer = await client_mod.invoke_a2a_peer(_peer(), "生成一张图")

    assert "对端不支持继续查询" in answer
    assert "-32601" in answer
    assert "任务 ID：j1" in answer


@pytest.mark.asyncio
async def test_poll_network_error_does_not_retry_second_endpoint(monkeypatch):  # noqa: ANN001
    """轮询内部异常不得冒泡到 endpoint 循环 —— 否则会对第二个端点重跑一遍整段轮询。"""
    _fast_poll(monkeypatch)
    captured: list[dict] = []

    class _Boom(_SeqClient):
        async def post(self, url: str, *, json: dict | None = None, headers: dict | None = None) -> _Resp:
            captured.append({"url": url, "body": json})
            if len(captured) == 1:
                return _Resp({"jsonrpc": "2.0", "id": "1", "result": _task("working")})
            raise client_mod.httpx.RequestError("boom")

    monkeypatch.setattr(client_mod.httpx, "AsyncClient", lambda **_kwargs: _Boom([], captured))

    answer = await client_mod.invoke_a2a_peer(_peer(), "生成一张图")

    assert "继续查询失败（网络异常）" in answer
    # 只有 message/send + 一次 tasks/get：第二个端点未被重试
    assert [item["url"] for item in captured] == [
        "https://peer.example.com/a2a/message/send",
        "https://peer.example.com/a2a/tasks/get",
    ]


@pytest.mark.asyncio
async def test_task_without_id_is_not_polled(monkeypatch):  # noqa: ANN001
    _fast_poll(monkeypatch)
    captured = _patch(monkeypatch, [{"jsonrpc": "2.0", "id": "1", "result": _task("working", task_id=None)}])

    answer = await client_mod.invoke_a2a_peer(_peer(), "生成一张图")

    assert "对端未给出任务 ID" in answer
    assert len(captured) == 1


@pytest.mark.asyncio
async def test_message_response_is_not_treated_as_task(monkeypatch):  # noqa: ANN001
    """回归：普通 ``Message`` 回答的路径不变。"""
    captured = _patch(monkeypatch, [{"jsonrpc": "2.0", "id": "1", "result": {"kind": "message", "role": "agent", "parts": [{"kind": "text", "text": "收到"}]}}])

    answer = await client_mod.invoke_a2a_peer(_peer(), "你好")

    assert answer == "收到"
    assert len(captured) == 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run python -m pytest tests/tenant/agents/test_a2a_client_invoke.py -q`

Expected: FAIL —— `AttributeError: module ... has no attribute 'TASK_POLL_INTERVAL_SECONDS'`

- [ ] **Step 3: 实现 `_tasks_get_payload` 与 `_resolve_agent_task`**

在 `client.py` 的 `_render_agent_task` 之后、`_extract_text_from_response` 之前插入：

```python
#: 轮询间隔与总上限。不设为配置项：60s 与 ``invoke_a2a_peer`` 的 httpx 单请求超时同量级，
#: 且单次调用上限直接等于「用户为这个外部 peer 多等多久」，按 peer 调参是另一个量级的运营面。
TASK_POLL_INTERVAL_SECONDS = 2.0
TASK_POLL_TIMEOUT_SECONDS = 60.0


def _tasks_get_payload(task_id: str) -> dict:
    """``tasks/get`` 的 JSON-RPC 请求体。"""
    return {"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "tasks/get", "params": {"id": task_id}}


async def _resolve_agent_task(client: httpx.AsyncClient, url: str, task: dict, headers: dict[str, str]) -> str:
    """把一个 ``Task`` 响应变成回答：已是停止轮询态就直接渲染，否则轮询到停止轮询态。

    **本函数不得向上抛 ``httpx.RequestError`` / ``ValueError``**：调用它的位置在
    ``invoke_a2a_peer`` 的 endpoint 循环内，那层的 ``except`` 会把这里的结果丢掉并对第二个
    endpoint 重跑一遍（最坏 120s 且用户拿不到任何结论）。
    """
    task_id = task.get("id")
    if not isinstance(task_id, str) or not task_id:
        return _render_agent_task(task, note="对端未给出任务 ID，无法继续查询")
    if _task_state(task) in STOP_POLLING_TASK_STATES:
        return _render_agent_task(task)

    deadline = time.monotonic() + TASK_POLL_TIMEOUT_SECONDS
    latest = task
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        # 先睡再查：首响应已是「刚提交」，立刻重查只会打一个空转请求。
        await asyncio.sleep(min(TASK_POLL_INTERVAL_SECONDS, remaining))
        try:
            resp = await client.post(url, json=_tasks_get_payload(task_id), headers=headers)
            if resp.status_code >= 400:
                return _render_agent_task(latest, note=f"继续查询失败（HTTP {resp.status_code}）")
            data = resp.json()
        except (httpx.RequestError, ValueError):
            return _render_agent_task(latest, note="继续查询失败（网络异常）")
        err = _jsonrpc_error(data)
        if err is not None:
            return _render_agent_task(latest, note=f"对端不支持继续查询（{err[0]} {err[1]}）")
        if not _looks_like_task(data):
            # 形状不认识不是失败信号：保留最后一次已知状态，继续等。
            continue
        latest = data["result"]
        if _task_state(latest) in STOP_POLLING_TASK_STATES:
            return _render_agent_task(latest)
    return _render_agent_task(latest, note=f"已等待 {int(TASK_POLL_TIMEOUT_SECONDS)} 秒")
```

`client.py` 顶部 import 块补 `import asyncio` 与 `import time`。

- [ ] **Step 4: 在 `invoke_a2a_peer` 里接线 Task 分流（三处替换）**

**4a.** `client.py:196-199` 的 endpoint 列表 → 对称两份：

```python
    message_endpoints = [
        urljoin(rpc_base + "/", "message/send"),
        rpc_base,
    ]
    #: 与 message_endpoints 逐位对称：探到哪一种部署形态，tasks/get 就打对应的那一个
    #: （否则每轮轮询都要先打一个必然 404 的请求，对端限流下等于白烧配额）。
    tasks_get_endpoints = [
        urljoin(rpc_base + "/", "tasks/get"),
        rpc_base,
    ]
```

**4b.** `client.py:202` 的循环改为按索引迭代，让当前形态可索引：

```python
        for index, url in enumerate(message_endpoints):
```

**4c.** `client.py:206-210` 的响应处理段（Task 3 已改过一次）：

```python
                err = _jsonrpc_error(data)
                if err is not None:
                    raise BadRequestError(f"调用外部 A2A Agent「{peer.name}」失败：对端返回错误 {err[0]} {err[1]}")
                text = _extract_text_from_response(data)
                if text:
                    return text
```

替换为：

```python
                err = _jsonrpc_error(data)
                if err is not None:
                    raise BadRequestError(f"调用外部 A2A Agent「{peer.name}」失败：对端返回错误 {err[0]} {err[1]}")
                if _looks_like_task(data):
                    return await _resolve_agent_task(client, tasks_get_endpoints[index], data["result"], headers)
                text = _extract_text_from_response(data)
                if text:
                    return text
```

- [ ] **Step 5: 运行测试确认通过**

Run: `uv run python -m pytest tests/tenant/agents/test_a2a_client_invoke.py tests/tenant/agents/test_a2a_client_auth.py -q`

Expected: PASS

- [ ] **Step 6: 反证 —— 确认新用例真的能抓缺陷**

临时把 `if _looks_like_task(data):` 与其 return 两行注释掉，重跑：

Run: `uv run python -m pytest tests/tenant/agents/test_a2a_client_invoke.py -q -k "not jsonrpc_error"`

Expected: FAIL —— `test_terminal_task_is_not_polled`、`test_polls_until_completed_and_reports_artifacts` 等多条转 RED（证明它们针对的是真实缺陷，而非顺带成立）。随后**恢复那两行**。

- [ ] **Step 7: 提交**

```bash
git add backend/packages/miles-portal/src/miles_portal/tenant/a2a/client.py backend/tests/tenant/agents/test_a2a_client_invoke.py
git commit -F - <<'EOF'
feat(a2a): 出站认识 Task 响应并以有限轮询取回结果

本平台 Server 在生成任务未就绪时回的正是纯 Task（无 message /
artifacts），Client 抽文本三条路径全落空后落到 str(result)[:4000]，把
原始 JSON 当回答写进主模型素材；两个实例互联时必然触发。

改为分流到有限轮询：2s 间隔、60s 上限，终态/中断态即停；超时或对端不
支持 tasks/get 时回退为状态快照 + taskId。tasks/get 与 message/send 的
endpoint 逐位对称，避免每轮打两次请求。
EOF
```

---

## Task 6: Client 侧出站 `tasks/cancel` 能力（只补，不调用）

**Files:**
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/a2a/client.py`
- Test: `backend/tests/tenant/agents/test_a2a_client_invoke.py`

**Interfaces:**
- Consumes: 现有 `_pick_rpc_url` / `build_auth_headers` / `_jsonrpc_error`
- Produces: `async cancel_a2a_peer_task(peer: A2aPeer, task_id: str) -> None`

- [ ] **Step 1: 写失败测试**

追加到 `backend/tests/tenant/agents/test_a2a_client_invoke.py`：

```python
@pytest.mark.asyncio
async def test_cancel_peer_task_sends_tasks_cancel(monkeypatch):  # noqa: ANN001
    captured = _patch(monkeypatch, [{"jsonrpc": "2.0", "id": "1", "result": _task("canceled")}])

    await client_mod.cancel_a2a_peer_task(_peer(), "j1")

    assert len(captured) == 1
    assert captured[0]["url"] == "https://peer.example.com/a2a/tasks/cancel"
    assert captured[0]["body"]["method"] == "tasks/cancel"
    assert captured[0]["body"]["params"] == {"id": "j1"}


@pytest.mark.asyncio
async def test_cancel_peer_task_raises_on_not_cancelable(monkeypatch):  # noqa: ANN001
    """对端明确拒绝时抛错，且不再探测第二个 endpoint（它已应答，形态已匹配）。"""
    captured = _patch(monkeypatch, [{"jsonrpc": "2.0", "id": "1", "error": {"code": -32002, "message": "任务已结束"}}])

    with pytest.raises(BadRequestError) as excinfo:
        await client_mod.cancel_a2a_peer_task(_peer(), "j1")

    assert "-32002" in str(excinfo.value)
    assert len(captured) == 1


@pytest.mark.asyncio
async def test_cancel_peer_task_tries_both_endpoints_before_giving_up(monkeypatch):  # noqa: ANN001
    """HTTP 层失败可能只是路径不对：两个形态都试过才认输。"""
    captured: list[dict] = []

    class _AllFail(_SeqClient):
        async def post(self, url: str, *, json: dict | None = None, headers: dict | None = None) -> _Resp:
            captured.append({"url": url, "body": json})
            return _Resp({}, status_code=500)

    monkeypatch.setattr(client_mod.httpx, "AsyncClient", lambda **_kwargs: _AllFail([], captured))

    with pytest.raises(BadRequestError):
        await client_mod.cancel_a2a_peer_task(_peer(), "j1")

    assert [item["url"] for item in captured] == [
        "https://peer.example.com/a2a/tasks/cancel",
        "https://peer.example.com/a2a",
    ]


@pytest.mark.asyncio
async def test_cancel_peer_task_rejects_inactive_peer(monkeypatch):  # noqa: ANN001
    peer = _peer()
    peer.status = SimpleNamespace(value="inactive")

    with pytest.raises(BadRequestError):
        await client_mod.cancel_a2a_peer_task(peer, "j1")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run python -m pytest tests/tenant/agents/test_a2a_client_invoke.py -q -k cancel`

Expected: FAIL —— `AttributeError: module ... has no attribute 'cancel_a2a_peer_task'`

- [ ] **Step 3: 实现**

在 `client.py` 的 `invoke_a2a_peer` 之后追加：

```python
async def cancel_a2a_peer_task(peer: A2aPeer, task_id: str) -> None:
    """请对端取消一个异步任务。成功返回；被拒或不可达抛 ``BadRequestError``。

    **本批没有任何调用方**：``invoke_a2a_peer`` 的轮询超时不会调用它。超时只表达「我不想
    再等了」，不等于「放弃这个任务」——而对端任务的产物落在对端租户、属于对端用户，贸然
    取消会把一个再过几秒就完成的任务连同产物一起销毁。这个函数是为「上游将来出现明确的
    放弃语义」（如用户显式中止）预留的能力。
    """
    if peer.status.value != "active" or not (peer.agent_card_json or {}):
        raise BadRequestError(f"外部 Agent「{peer.name}」尚未同步 Agent Card 或未连通")
    rpc_base = _pick_rpc_url(peer)
    if not rpc_base:
        raise BadRequestError(f"外部 Agent「{peer.name}」的 Card 未声明可调用的 JSON-RPC 端点")

    payload = {"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "tasks/cancel", "params": {"id": task_id}}
    headers = {**JSONRPC_HEADERS, **build_auth_headers(peer.auth_config)}
    endpoints = [urljoin(rpc_base + "/", "tasks/cancel"), rpc_base]
    last_err: str | None = None
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        for url in endpoints:
            try:
                resp = await client.post(url, json=payload, headers=headers)
            except httpx.RequestError as exc:
                last_err = str(exc)
                continue
            if resp.status_code >= 400:
                last_err = f"HTTP {resp.status_code}"
                continue
            try:
                data = resp.json()
            except ValueError:
                last_err = "响应非 JSON"
                continue
            err = _jsonrpc_error(data)
            if err is not None:
                # 对端已按 JSON-RPC 应答，说明端点形态已匹配：不再试下一个。
                raise BadRequestError(f"取消外部 A2A Agent「{peer.name}」的任务失败：对端返回错误 {err[0]} {err[1]}")
            return
    raise BadRequestError(f"取消外部 A2A Agent「{peer.name}」的任务失败" + (f"：{last_err}" if last_err else ""))
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run python -m pytest tests/tenant/agents/test_a2a_client_invoke.py -q`

Expected: PASS

- [ ] **Step 5: 确认无调用方**

Run: `rg -n "cancel_a2a_peer_task" backend/packages/ | grep -v "def cancel_a2a_peer_task"`

Expected: 无输出（函数定义之外的任何引用都必须为零）

- [ ] **Step 6: 提交**

```bash
git add backend/packages/miles-portal/src/miles_portal/tenant/a2a/client.py backend/tests/tenant/agents/test_a2a_client_invoke.py
git commit -F - <<'EOF'
feat(a2a): 补出站 tasks/cancel 能力（本批不自动调用）

Server 侧早有 tasks/cancel，出站侧缺失。补上对称 endpoint 探测与明确
的失败契约（对端拒绝即抛错、HTTP 层失败才试下一个形态），但不在任何
路径调用它。

超时不等于放弃：对端任务的产物落在对端租户、属于对端用户，轮询等不到
就取消会把即将完成的产物一起销毁。待上游出现显式中止语义时再接。
EOF
```

---

## Task 7: 文档同步与全量质量门

**Files:**
- Modify: `docs/guides/a2a.md`
- Modify: `docs/features/a2a-interconnect.md`

**Interfaces:**
- Consumes: 前 6 个任务的全部行为
- Produces: 无代码符号

- [ ] **Step 1: 更新 `docs/guides/a2a.md`**

在「平台内引用外部（custom）」段补出站行为，需覆盖三条：

1. Client 收到 `Task` 后会以 2s 间隔轮询 `tasks/get`，**至多 60s**；终态时把产物渲染为引用清单（`name` / `mimeType` / `uri`），**不下载内容**；超时或对端不支持 `tasks/get`（`-32601`）时回退为「状态快照 + `taskId`」，由上层自行继续查询
2. 对端返回 JSON-RPC `error` 视为**调用失败**（经 `invoke.py` 记为 `a2a_error`），不再把错误消息当回答
3. 中断态（`input-required` / `auth-required`）停止轮询并如实回报；`input-required` 时对端的提问写在 `status.message` 里，会一并带回

在 `tasks/get` 段补语义：`status.timestamp` 是该任务状态被记录的**真实时间**（`updated_at`），`status.message` 带进度文案与 `metadata.percent`。**同时明确 `message/send` 的例外**：它返回的提交快照用请求时刻，因为上游只给出 `{id, kind, status}`，拿不到真实时间。

在「审计」段附近或轮询段补一句：出站轮询会给对端带来额外负载（每次 Task 响应最多 30 次 `tasks/get`），受对端自己的 `scope = api_key` 限流约束；Client 侧不主动降频。

- [ ] **Step 2: 更新 `docs/features/a2a-interconnect.md`**

同步出站行为（轮询、产物引用、error 判失败、中断态停止），并更新错误码/形状小节里与 `tasks/get` 的 `status` 相关的描述。

- [ ] **Step 3: 标记清点缺口为已关闭**

在 `docs/superpowers/specs/2026-09-21-a2a-task-status-and-outbound-poll-design.md` 的 §5 之外无需改动；若有别的文档登记过以下四条缺口，逐条标记关闭：

- 出站无 `tasks/get` 轮询
- `tasks/get` 的 `status.timestamp` 用请求时刻
- `tasks/get` 不返回 `status.message`
- 对端错误消息冒充回答

- [ ] **Step 4: 全量质量门**

Run: `uv run python -m pytest -q`

Expected: PASS（全量，含既有 1400+ 用例）

Run: `uv run ruff check .`

Expected: 无输出（零告警）

Run: `uv run ruff format --check .`

Expected: 无输出（无需格式化）

Run: `make layers-check`

Expected: PASS

Run: `make openapi-check`

Expected: PASS。若因 docstring 变化导致快照漂移，按仓库既有做法更新 `backend/openapi/openapi.snapshot.json` 后重跑

- [ ] **Step 5: 提交**

```bash
git add docs/ backend/openapi/openapi.snapshot.json
git commit -F - <<'EOF'
docs(a2a): 同步出站轮询、error 判失败与 Task 状态语义

补齐出站行为（2s/60s 有限轮询、产物只给引用、中断态停止轮询）、
tasks/get 的 status.timestamp 与 status.message 语义，并写明
message/send 提交快照仍用请求时刻的例外与原因。
EOF
```

---

## Self-Review

**1. Spec 覆盖**

| Spec 章节 | 落点 |
|---|---|
| §3.1 判据与分流（`_jsonrpc_error` / `_looks_like_task` / `_task_state` / 分流顺序 / try 约束） | Task 3 Step 3-4、Task 4 Step 3、Task 5 Step 4（含网络异常不重试第二个端点的用例） |
| §3.2 有限轮询（常量、四步流程、失败终止、形状不认识继续等） | Task 5 Step 3 + `test_timeout_returns_snapshot_with_task_id` / `test_poll_jsonrpc_error_falls_back_to_snapshot` / `test_poll_network_error_does_not_retry_second_endpoint` |
| §3.3 渲染（按状态首行、进度、产物、taskId、note、不带 peer 名） | Task 4（含 6 条 headline 参数化用例） |
| §3.4 endpoint 对称探测 | Task 5 Step 3-4 + `test_polls_with_symmetric_endpoint` |
| §3.5 `cancel_a2a_peer_task`（只补不调用） | Task 6（含 4 条用例 + 无调用方校验） |
| §3.6 `build_a2a_task_status` 抽取 + `build_a2a_task` 支持 text/percent | Task 1 |
| §3.7 `timestamp_iso` 与 5 个调用点（3 改 2 不变） | Task 1 Step 3、Task 2 Step 5-8（Step 8 显式核对两处不变） |
| §3.8 测试面（含反证要求） | Task 5 Step 6 反证；其余散在各 Task |
| §3.9 文档 | Task 7 |
| §2 决策 1-8 | 决策 1/3 → Global Constraints；决策 2 → Task 4/5；决策 4/5 → Task 2 Step 8；决策 6 → 无（结构选择已体现在文件表）；决策 7 → Task 6；决策 8 → Task 3 |
| §5 第 6 条（`percent` 无 `text` 时丢弃） | 既有行为，Task 1 Step 3 的实现逐字保留了该语义（`text is None` 时提前 return） |
| §6 验收清单 | 逐条对应上述用例；最后一条 → Task 7 Step 4 |

**2. 占位符扫描**

无占位符。原先三处不确定项已在写计划期间实地核对并替换为真名/真行为：

- `test_a2a_task_resubscribe.py` 的驱动方式 → 实地确认为 `_scripted` + `open_task_subscription` + `_json_frames`（`_json_frames` 定义在该文件 `:110`），已写入真实调用
- `services/server.py` 的 import 面 → 实地确认 `progress_text` **未**被 import（原计划漏了它），已补
- `subscription.py` 的 import 面 → 实地确认 `progress_text` **已** import，计划已改为只加 `timestamp_iso`

**3. 实现前的事实核对（写计划期间发现并已修正的 4 个缺陷）**

| 缺陷 | 若不修正的后果 |
|---|---|
| 原「`status_from_task == status_from_update`」断言 | `build_a2a_agent_message` 用 `uuid4()` 生成 `messageId`（`server.py:314`），两次构造必然不等 —— 该测试永远红。已改为剔除 `messageId` 后比较形状 |
| 原只列了 2 处需补字段的替身 | 实际是 **4 处**：`test_a2a_server_card.py::_job`(:830) 与 `tasks/cancel` 内联 `cancel_job` 返回值(:941) 都缺 `progress_message`/`progress_percent`/`updated_at` 三个字段，接线后该文件全部 `tasks/get`/`tasks/cancel` 成功路径会 AttributeError。已列全并标注两处无需改的替身 |
| 原 Task 2 Step 5 只加 `timestamp_iso` | `progress_text` 在 `services/server.py` 里从未被 import，接线即 NameError。已改为补两个符号 |
| 原 Task 5 Step 4 把两处不相邻的改动写成一段 | `endpoints` 定义（:196）与 `for url in endpoints:`（:202）之间隔着一个 `async with`，一次替换做不完。已拆成 4a/4b/4c |

**4. 类型与命名一致性**

- `_render_agent_task(task, *, note=None)` —— Task 4 定义，Task 5 的 4 处调用一致（无 `peer_name` 参数）
- `_resolve_agent_task(client, url, task, headers)` —— Task 5 定义与 `invoke_a2a_peer` 内调用一致（4 个位置参数）
- `_jsonrpc_error` 返回 `tuple[object, str] | None` —— Task 3 定义，Task 5 的轮询里按 `err[0]` / `err[1]` 解包一致
- `timestamp_iso(value: datetime | None) -> str` —— Task 1 定义，Task 2 三处调用一致
- `build_a2a_task_status` 的 `message_task_id` / `job_task_id` —— Task 1 定义，`build_a2a_task` 只传前者、`build_a2a_status_update` 传两者，与 spec §3.6 一致
- 常量 `TASK_POLL_INTERVAL_SECONDS` / `TASK_POLL_TIMEOUT_SECONDS` / `STOP_POLLING_TASK_STATES` / `TERMINAL_TASK_STATES` / `INTERRUPTED_TASK_STATES` —— Task 4/5 定义，测试与 `_resolve_agent_task` 引用一致
- `BadRequestError` 继承链已核实为 `AppError(Exception)`（非 `ValueError` 子类），故 Task 3 的 `raise` 落在 `except ValueError` 的 `try` 内是安全的
