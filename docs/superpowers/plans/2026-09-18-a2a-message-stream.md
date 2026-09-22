# A2A `message/stream` 真流式 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让本平台发布的 A2A Server 支持 `message/stream`（SSE 真 token 流式），并把 Card 的协议版本声明从 `1.0` 修正为与实现一致的 `0.3`。

**Architecture:** 复用既有真流链路（`AgentService.chat(..., on_delta=)` → LiteLLM 逐 chunk 回调），在 `miles_portal` 用例层用「后台 asyncio 任务 + 有界队列」把增量转成 SSE 帧；纯逻辑模块只负责帧形状构造；视图层按 JSON-RPC `method` 分流，`message/stream` 返回 `StreamingResponse`，其余方法不变。

**Tech Stack:** Python 3.12 / FastAPI / Starlette `StreamingResponse` / asyncio / SQLAlchemy AsyncSession / pytest(asyncio)

**Spec:** `docs/superpowers/specs/2026-09-18-a2a-message-stream-design.md`

## Global Constraints

- **Commit message 必须简体中文**，格式 `<type>(<scope>): <简述>`，用 HEREDOC 传递；专有名词可英文（A2A、SSE、JSON-RPC、Task、Card）。
- **质量门**（每个任务提交前至少跑相关子集，最终任务须全绿）：`make lint-backend format-check-backend layers-check openapi-check test-backend`。
- **OpenAPI 快照不得变化**：本批不新增路由与 schema；`openapi-check` 若报差异，先怀疑视图函数的返回类型标注（见 Task 5）。
- **纯逻辑模块 `miles_portal/tenant/a2a/server.py` 不得 import ORM / DB**（该模块被 `miles_openapi` 声明层直接 import，`layers-check` 会拦）。
- **线格式一律 v0.3**：`kind` 判别字段、小写 TaskState、`message/*` 方法名。**不得**引入 v1.0 的成员名包装（`{"statusUpdate":…}`）或 `TASK_STATE_*` 取值。
- 测试命令统一形如 `cd backend && uv run python -m pytest -q <path>`；**不要**用 `uv run pytest tests/...`（该仓库在此会 `ModuleNotFoundError: No module named 'tests'`）。
- 断言 SSE 帧时，`data:` 单行 JSON、帧间以空行分隔（`\n\n`）；JSON 用 `ensure_ascii=False` 序列化，中文按原样出网。

---

### Task 1: 纯逻辑层线格式对齐与 Card 声明

**Files:**
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/a2a/server.py`
- Test: `backend/tests/tenant/a2a/test_a2a_server_card.py`

**Interfaces:**
- Consumes: 无（首个任务）
- Produces:
  - `A2A_PROTOCOL_VERSION == "0.3"`
  - `TASK_STATE_REJECTED == "rejected"`
  - `build_a2a_agent_message(*, text: str, context_id: str, task_id: str | None = None) -> dict`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/tenant/a2a/test_a2a_server_card.py` 的 import 段（`from miles_portal.tenant.a2a.server import (...)`）加入 `build_a2a_agent_message`；然后在「1. 纯函数」区块末尾（`test_jsonrpc_envelopes` 之前）追加：

```python
def test_build_agent_card_declares_streaming_and_v03():
    """声明必须与实现同版：方法名/payload 全是 0.3，Card 就不能标 1.0。"""
    card = build_agent_card(agent_id=AGENT_ID, name="客服助手", description="D", base_url=BASE)

    assert card["protocolVersion"] == "0.3"
    assert card["capabilities"]["streaming"] is True
    assert card["additionalInterfaces"] == [{"url": rpc_url, "transport": "JSONRPC"}]


def test_task_state_rejected_constant_exists():
    """合规拦截要回 A2A ``rejected``（拒绝处理），不借用 ``failed``。"""
    assert server_mod.TASK_STATE_REJECTED == "rejected"


def test_build_a2a_agent_message_shape():
    message = build_a2a_agent_message(text="订单已发货", context_id="ctx-1")

    assert message["kind"] == "message"
    assert message["role"] == "agent"
    assert message["contextId"] == "ctx-1"
    # 0.3 的 Part 判别键是 kind：发 type 会被严格的对端当未知 part 丢掉
    assert message["parts"] == [{"kind": "text", "text": "订单已发货"}]
    assert message["messageId"]
    assert "taskId" not in message


def test_build_a2a_agent_message_carries_task_id_when_given():
    message = build_a2a_agent_message(text="增量", context_id="ctx-1", task_id="t-1")

    assert message["taskId"] == "t-1"


def test_build_a2a_artifacts_part_kind_is_file():
    artifacts = build_a2a_artifacts(
        job_result={"kind": "image", "attachment_ids": ["att-1"], "mime_type": "image/png"},
        agent_id=AGENT_ID,
        task_id=uuid4(),
        base_url=BASE,
    )

    assert artifacts[0]["parts"][0]["kind"] == "file"
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && uv run python -m pytest -q tests/tenant/a2a/test_a2a_server_card.py
```
Expected: FAIL —— `ImportError: cannot import name 'build_a2a_agent_message'`；`TASK_STATE_REJECTED` 断言 AttributeError；`streaming`/`protocolVersion`/`["kind"]` 断言不成立。

- [ ] **Step 3: 实现**

`backend/packages/miles-portal/src/miles_portal/tenant/a2a/server.py`：

(a) import 段补 `uuid4`：

```python
from uuid import UUID, uuid4
```

(b) 常量：版本改 0.3、注释改 v0.3、补 `rejected`：

```python
#: Agent Card 声明的协议版本与传输绑定。
#: 取值 0.3：本模块产出的方法名（``message/*``、``tasks/*``）与线格式（``kind`` 判别字段、
#: 小写 TaskState）都是 v0.3 形状。声明 1.0 会让对端按 PascalCase 方法名调用并撞 ``-32601``。
A2A_PROTOCOL_VERSION = "0.3"
A2A_PROTOCOL_BINDING = "JSONRPC"
```

```python
#: A2A ``TaskState``（v0.3）。
TASK_STATE_SUBMITTED = "submitted"
TASK_STATE_WORKING = "working"
TASK_STATE_COMPLETED = "completed"
TASK_STATE_FAILED = "failed"
TASK_STATE_CANCELED = "canceled"
TASK_STATE_REJECTED = "rejected"
TASK_STATE_UNKNOWN = "unknown"
```

(c) `build_agent_card` 里 `streaming` 改 `True`：

```python
        "capabilities": {
            "streaming": True,
            "pushNotifications": False,
            "stateTransitionHistory": False,
        },
```

(d) 在 `build_a2a_task` 之后新增消息构造函数：

```python
def build_a2a_agent_message(*, text: str, context_id: str, task_id: str | None = None) -> dict:
    """A2A ``Message``（agent 角色）。

    ``contextId`` 必须回显：对端据此把后续消息接回同一上下文，否则每轮都是新对话。
    ``taskId`` 仅在该消息属于某个 Task 时带上（流式帧的嵌套消息带，``message/send``
    的同步回答不带 —— 同步回答不产生任务）。
    """
    message: dict = {
        "kind": "message",
        "role": "agent",
        "messageId": str(uuid4()),
        "contextId": context_id,
        "parts": [{"kind": "text", "text": text}],
    }
    if task_id:
        message["taskId"] = task_id
    return message
```

(e) `build_a2a_artifacts` 里 part 判别键 `type` → `kind`：

```python
        artifacts.append(
            {
                "artifactId": attachment_id,
                "parts": [{"kind": "file", "file": file}],
            }
        )
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd backend && uv run python -m pytest -q tests/tenant/a2a/test_a2a_server_card.py
```
Expected: PASS（全文件）。注意既有 `test_build_agent_card_declares_rpc_interface_and_fallback_skill` 断言
`card["additionalInterfaces"] == [{"url": rpc_url, "transport": "JSONRPC"}]`。

- [ ] **Step 5: 提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI && git add \
  backend/packages/miles-portal/src/miles_portal/tenant/a2a/server.py \
  backend/tests/tenant/a2a/test_a2a_server_card.py && git commit -F - <<'EOF'
fix(a2a): Card 声明改为 0.3 并统一 Part 判别键

原先声明 protocolVersion=1.0，方法名与线格式却全是 0.3（kind 判别字段、
小写 TaskState、message/* 方法名）—— 按 1.0 调用的客户端会撞 -32601。
同批把出站 Part 判别键从 type 改为 0.3 规定的 kind，并补 rejected 状态
（合规拦截要用它表达「拒绝处理」而非「执行失败」）。
EOF
```

---

### Task 2: 出站请求判别键对齐

**Files:**
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/a2a/client.py:188`
- Test: `backend/tests/tenant/agents/test_a2a_client_auth.py`

**Interfaces:**
- Consumes: 无
- Produces: 出站 `message/send` 请求体 `params.message.parts == [{"kind": "text", "text": <task>}]`

- [ ] **Step 1: 写失败测试**

`backend/tests/tenant/agents/test_a2a_client_auth.py`：

(a) `_FakeClient.post` 增加请求体捕获（`json` 现在是入参但没被记录）：

```python
    async def post(self, url: str, *, json: dict | None = None, headers: dict | None = None) -> _FakeResponse:
        self._captured["post"] = headers or {}
        self._captured["post_body"] = json
        self._captured.setdefault("post_urls", []).append(url)
        return _FakeResponse(self._post_data)
```

(b) `test_invoke_a2a_peer_sends_configured_auth` 末尾追加断言：

```python
    # 0.3 的 Part 判别键是 kind：发 type 会被严格的对端当未知 part 丢掉
    assert captured["post_body"]["params"]["message"]["parts"] == [{"kind": "text", "text": "你好"}]
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && uv run python -m pytest -q tests/tenant/agents/test_a2a_client_auth.py
```
Expected: FAIL —— `assert [{'type': 'text', ...}] == [{'kind': 'text', ...}]`。

- [ ] **Step 3: 实现**

`client.py` 的 `invoke_a2a_peer` 请求体：

```python
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": task}],
            },
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd backend && uv run python -m pytest -q tests/tenant/agents/test_a2a_client_auth.py tests/tenant/agents/test_a2a_extract_text.py tests/tenant/agents/test_a2a_invoke_rules.py
```
Expected: PASS（三个文件全绿；响应解析只读 `text`，对判别键无假设，故不受影响）。

- [ ] **Step 5: 提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI && git add \
  backend/packages/miles-portal/src/miles_portal/tenant/a2a/client.py \
  backend/tests/tenant/agents/test_a2a_client_auth.py && git commit -F - <<'EOF'
fix(a2a): 出站请求 Part 判别键改用 kind

平台发出的 message/send 请求体用 type 作 part 判别键，既不是 0.3 的 kind
也不是 1.0 的裸成员名：严格对端会把整段文本当未知 part 丢掉，而本平台
自己的入站解析只读 text 故没暴露问题。
EOF
```

---

### Task 3: 流式帧纯构造函数

**Files:**
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/a2a/server.py`
- Test: `backend/tests/tenant/a2a/test_a2a_server_card.py`

**Interfaces:**
- Consumes: Task 1 的 `build_a2a_agent_message`
- Produces:
  - `build_a2a_status_update(*, task_id: str, context_id: str, state: str, timestamp: str, text: str | None = None, final: bool = False, job_task_id: str | None = None) -> dict`

- [ ] **Step 1: 写失败测试**

在 `test_a2a_server_card.py` 的 import 段加入 `build_a2a_status_update`，并在 Task 1 新增的测试之后追加：

```python
def test_build_a2a_status_update_increment_frame():
    """中间帧：state=working、final=False，文本为本片增量，嵌套消息带 taskId/contextId。"""
    frame = build_a2a_status_update(
        task_id="t-1",
        context_id="ctx-1",
        state=server_mod.TASK_STATE_WORKING,
        timestamp="2026-09-18T09:00:00+00:00",
        text="甲",
        final=False,
    )

    assert frame["kind"] == "status-update"
    assert frame["taskId"] == "t-1"
    assert frame["contextId"] == "ctx-1"
    assert frame["final"] is False
    assert frame["status"]["state"] == "working"
    assert frame["status"]["timestamp"] == "2026-09-18T09:00:00+00:00"
    assert frame["status"]["message"]["taskId"] == "t-1"
    assert frame["status"]["message"]["contextId"] == "ctx-1"
    assert frame["status"]["message"]["parts"] == [{"kind": "text", "text": "甲"}]


def test_build_a2a_status_update_final_frame_carries_full_answer():
    frame = build_a2a_status_update(
        task_id="t-1",
        context_id="ctx-1",
        state=server_mod.TASK_STATE_COMPLETED,
        timestamp="2026-09-18T09:00:01+00:00",
        text="甲乙丙",
        final=True,
    )

    assert frame["final"] is True
    assert frame["status"]["state"] == "completed"
    assert frame["status"]["message"]["parts"][0]["text"] == "甲乙丙"
    assert "metadata" not in frame["status"]["message"]


def test_build_a2a_status_update_exposes_job_task_id_in_metadata():
    """本轮产生异步生成任务时，末帧给出真实 job id，对端才能转向 tasks/get 轮询产物。"""
    frame = build_a2a_status_update(
        task_id="t-1",
        context_id="ctx-1",
        state=server_mod.TASK_STATE_WORKING,
        timestamp="2026-09-18T09:00:00+00:00",
        text="正在生成",
        final=True,
        job_task_id="job-1",
    )

    assert frame["status"]["message"]["metadata"] == {"a2aJobTaskId": "job-1"}


def test_build_a2a_status_update_omits_message_without_text():
    """无文本终态不带 message（保留表达能力：终态可以只是状态）。"""
    frame = build_a2a_status_update(
        task_id="t-1",
        context_id="ctx-1",
        state=server_mod.TASK_STATE_FAILED,
        timestamp="2026-09-18T09:00:00+00:00",
        final=True,
    )

    assert "message" not in frame["status"]
    assert "metadata" not in frame
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && uv run python -m pytest -q tests/tenant/a2a/test_a2a_server_card.py
```
Expected: FAIL —— `ImportError: cannot import name 'build_a2a_status_update'`。

- [ ] **Step 3: 实现**

在 `server.py` 的 `build_a2a_agent_message` 之后新增：

```python
def build_a2a_status_update(
    *,
    task_id: str,
    context_id: str,
    state: str,
    timestamp: str,
    text: str | None = None,
    final: bool = False,
    job_task_id: str | None = None,
) -> dict:
    """A2A ``TaskStatusUpdateEvent``（``message/stream`` 的帧载荷）。

    ``final`` 表示「本流结束」，不等于「任务终态」—— 产生异步生成任务时以
    ``working`` + ``final=True`` 收尾，对端再转向 ``tasks/get`` 轮询。

    ``job_task_id`` 非空时写入嵌套消息的 ``metadata.a2aJobTaskId``：本流的 taskId 是
    合成的（流开始时就得定），生成任务 id 只有跑完才知道，故不强行合一，改用该扩展位
    把两者串起来。
    """
    status: dict = {"state": state, "timestamp": timestamp}
    if text is not None:
        message = build_a2a_agent_message(text=text, context_id=context_id, task_id=task_id)
        if job_task_id:
            message["metadata"] = {"a2aJobTaskId": job_task_id}
        status["message"] = message
    return {
        "kind": "status-update",
        "taskId": task_id,
        "contextId": context_id,
        "status": status,
        "final": final,
    }
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd backend && uv run python -m pytest -q tests/tenant/a2a/test_a2a_server_card.py
```
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI && git add \
  backend/packages/miles-portal/src/miles_portal/tenant/a2a/server.py \
  backend/tests/tenant/a2a/test_a2a_server_card.py && git commit -F - <<'EOF'
feat(a2a): 新增 message/stream 的帧构造纯函数

增量以 status-update 帧下发（官方 SDK 示例同形状），末帧带完整回答，使对端
丢帧也能补全。异步生成任务的真实 job id 经 metadata 扩展位给出，避免把
「流开始前就得定的合成 taskId」与「跑完才知道的 job id」强行合一。
EOF
```

---

### Task 4: 用例层 `open_a2a_stream`

**Files:**
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/server.py`
- Test: `backend/tests/tenant/a2a/test_a2a_server_card.py`

**Interfaces:**
- Consumes: Task 1/3 的 `build_a2a_agent_message` / `build_a2a_status_update` / `TASK_STATE_*`；既有 `build_a2a_task`、`_first_active_job`、`load_published_agent`、`extract_message_text`、`extract_message_context_id`
- Produces:
  - `run_published_agent_chat(db, ctx, agent_id, text, *, conversation_id=None, on_delta=None) -> ChatResponse`（新增 `on_delta` 透传）
  - `open_a2a_stream(db, ctx, agent_id, payload) -> dict | AsyncIterator[str]`

- [ ] **Step 1: 写失败测试**

`test_a2a_server_card.py` 顶部 import 段补 `import asyncio`（若尚未导入）、`import json`，并把既有 `test_handle_rpc_message_send_returns_agent_message` 的断言补上判别键：

```python
    assert result["parts"][0]["kind"] == "text"
```

然后在该文件末尾（新开区块注释 `# --- 6. message/stream ---`）追加：

```python
class _FakeSession:
    """``AsyncSessionLocal()`` 替身：流式生成器内部自开会话，测试须替换掉真实连接。"""

    def __init__(self) -> None:
        self.committed = 0
        self.rolled_back = 0

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False

    async def commit(self) -> None:
        self.committed += 1

    async def rollback(self) -> None:
        self.rolled_back += 1


def _patch_session(monkeypatch, session: _FakeSession) -> None:  # noqa: ANN001
    monkeypatch.setattr(server_svc, "AsyncSessionLocal", lambda: session)


async def _collect(stream) -> list[dict]:  # noqa: ANN001
    """把 SSE 帧解回 JSON 信封，便于断言形状。"""
    frames: list[dict] = []
    async for frame in stream:
        assert frame.startswith("data: ")
        assert frame.endswith("\n\n")
        frames.append(json.loads(frame[len("data: ") : -2]))
    return frames


def _stream_params(text: str = "写点什么", context_id: str | None = None) -> dict:
    message: dict = {"parts": [{"kind": "text", "text": text}]}
    if context_id:
        message["contextId"] = context_id
    return {"jsonrpc": "2.0", "id": 1, "method": "message/stream", "params": {"message": message}}


@pytest.mark.asyncio
async def test_open_stream_preflight_failure_returns_error_envelope():
    """未发布智能体必须在 SSE 开始前回普通 JSON：流一旦开始，错误只能塞进帧里。"""
    opened = await server_svc.open_a2a_stream(
        _Db(agent=None), SimpleNamespace(), AGENT_ID, _stream_params()
    )

    assert isinstance(opened, dict)
    assert opened["error"]["code"] == server_mod.INVALID_PARAMS


@pytest.mark.asyncio
async def test_open_stream_rejects_bad_params_before_streaming():
    opened = await server_svc.open_a2a_stream(
        _Db(agent=_agent()), SimpleNamespace(), AGENT_ID, _stream_params(text="   ")
    )

    assert isinstance(opened, dict)
    assert opened["error"]["code"] == server_mod.INVALID_PARAMS


@pytest.mark.asyncio
async def test_open_stream_rejects_missing_params_before_streaming():
    payload = {"jsonrpc": "2.0", "id": 1, "method": "message/stream"}
    opened = await server_svc.open_a2a_stream(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, payload)

    assert isinstance(opened, dict)
    assert opened["error"]["code"] == server_mod.INVALID_PARAMS


@pytest.mark.asyncio
async def test_open_stream_emits_task_then_increments_then_final(monkeypatch):  # noqa: ANN001
    """真流路由：首帧 Task、中间帧逐片增量、末帧 completed 且带完整回答。"""
    session = _FakeSession()
    _patch_session(monkeypatch, session)
    seen: dict = {}

    async def fake_chat(_db, _ctx, _agent_id, text, conversation_id=None, on_delta=None):  # noqa: ANN001
        seen["text"] = text
        seen["conversation_id"] = conversation_id
        await on_delta("甲")
        await on_delta("乙")
        return ChatResponse(answer="甲乙")

    monkeypatch.setattr(server_svc, "run_published_agent_chat", fake_chat)
    stream = await server_svc.open_a2a_stream(
        _Db(agent=_agent()), SimpleNamespace(), AGENT_ID, _stream_params(text="写点什么", context_id="ctx-7")
    )

    frames = await _collect(stream)
    results = [f["result"] for f in frames]

    assert all(f["jsonrpc"] == "2.0" and f["id"] == 1 for f in frames)
    assert results[0]["kind"] == "task"
    assert results[0]["status"]["state"] == "working"
    assert results[0]["contextId"] == "ctx-7"

    mids = results[1:-1]
    assert [m["status"]["message"]["parts"][0]["text"] for m in mids] == ["甲", "乙"]
    assert all(m["final"] is False for m in mids)
    assert all(m["taskId"] == results[0]["id"] for m in mids)

    last = results[-1]
    assert last["final"] is True
    assert last["status"]["state"] == "completed"
    assert last["status"]["message"]["parts"][0]["text"] == "甲乙"

    assert seen["text"] == "写点什么"
    assert seen["conversation_id"] == "ctx-7"
    assert session.committed == 1


@pytest.mark.asyncio
async def test_open_stream_generates_context_id_when_absent(monkeypatch):  # noqa: ANN001
    """首轮未带 contextId 时生成一个并作为 conversation_id 下传，多轮才接得上。"""
    _patch_session(monkeypatch, _FakeSession())
    seen: dict = {}

    async def fake_chat(_db, _ctx, _agent_id, _text, conversation_id=None, on_delta=None):  # noqa: ANN001
        seen["conversation_id"] = conversation_id
        return ChatResponse(answer="好的")

    monkeypatch.setattr(server_svc, "run_published_agent_chat", fake_chat)
    stream = await server_svc.open_a2a_stream(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, _stream_params())

    results = [f["result"] for f in await _collect(stream)]

    assert seen["conversation_id"]
    assert results[0]["contextId"] == seen["conversation_id"]


@pytest.mark.asyncio
async def test_open_stream_one_shot_route_only_has_final_frame(monkeypatch):  # noqa: ANN001
    """不接 on_delta 的路由（flow/子智能体等）不产生中间帧，靠末帧一次给全。"""
    _patch_session(monkeypatch, _FakeSession())

    async def fake_chat(_db, _ctx, _agent_id, _text, conversation_id=None, on_delta=None):  # noqa: ANN001
        return ChatResponse(answer="完整回答")

    monkeypatch.setattr(server_svc, "run_published_agent_chat", fake_chat)
    stream = await server_svc.open_a2a_stream(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, _stream_params())

    results = [f["result"] for f in await _collect(stream)]

    assert len(results) == 2
    assert results[0]["kind"] == "task"
    assert results[-1]["status"]["state"] == "completed"
    assert results[-1]["status"]["message"]["parts"][0]["text"] == "完整回答"


@pytest.mark.asyncio
async def test_open_stream_maps_compliance_block_to_rejected(monkeypatch):  # noqa: ANN001
    """输入/输出合规拦截回 rejected（拒绝处理），并把原因交给对端。"""
    session = _FakeSession()
    _patch_session(monkeypatch, session)

    async def fake_chat(_db, _ctx, _agent_id, _text, conversation_id=None, on_delta=None):  # noqa: ANN001
        await on_delta("部分")
        raise BadRequestError("输出内容包含敏感词，已拦截：测试")

    monkeypatch.setattr(server_svc, "run_published_agent_chat", fake_chat)
    stream = await server_svc.open_a2a_stream(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, _stream_params())

    results = [f["result"] for f in await _collect(stream)]
    last = results[-1]

    assert last["final"] is True
    assert last["status"]["state"] == "rejected"
    assert "敏感词" in last["status"]["message"]["parts"][0]["text"]
    assert session.rolled_back == 1


@pytest.mark.asyncio
async def test_open_stream_maps_execution_failure_to_failed(monkeypatch):  # noqa: ANN001
    _patch_session(monkeypatch, _FakeSession())

    async def fake_chat(_db, _ctx, _agent_id, _text, conversation_id=None, on_delta=None):  # noqa: ANN001
        raise RuntimeError("boom")

    monkeypatch.setattr(server_svc, "run_published_agent_chat", fake_chat)
    stream = await server_svc.open_a2a_stream(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, _stream_params())

    last = [f["result"] for f in await _collect(stream)][-1]

    assert last["final"] is True
    assert last["status"]["state"] == "failed"
    assert "boom" in last["status"]["message"]["parts"][0]["text"]


@pytest.mark.asyncio
async def test_open_stream_hands_off_job_id_via_metadata(monkeypatch):  # noqa: ANN001
    """产生异步生成任务时以 working/final 收尾，并给出真实 job id 供对端轮询。"""
    _patch_session(monkeypatch, _FakeSession())

    async def fake_chat(_db, _ctx, _agent_id, _text, conversation_id=None, on_delta=None):  # noqa: ANN001
        return ChatResponse(answer="正在生成", generative_jobs=[{"id": "job-1", "kind": "video", "status": "pending"}])

    monkeypatch.setattr(server_svc, "run_published_agent_chat", fake_chat)
    stream = await server_svc.open_a2a_stream(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, _stream_params())

    last = [f["result"] for f in await _collect(stream)][-1]

    assert last["final"] is True
    assert last["status"]["state"] == "working"
    assert last["status"]["message"]["metadata"] == {"a2aJobTaskId": "job-1"}
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && uv run python -m pytest -q tests/tenant/a2a/test_a2a_server_card.py
```
Expected: FAIL —— `AttributeError: module ... has no attribute 'open_a2a_stream'`（`AsyncSessionLocal` 也尚未导入）；`parts[0]["kind"]` 断言失败（现在发 `type`）。

- [ ] **Step 3: 实现**

`backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/server.py`：

(a) import 段补（**`json` 必须有**，`_sse_frame` 用它序列化）：

```python
import asyncio
import json
from collections.abc import AsyncIterator
```

```python
from miles_core.infra.db import AsyncSessionLocal
```

```python
from miles_portal.tenant.a2a.server import (
    ...
    TASK_STATE_COMPLETED,
    TASK_STATE_FAILED,
    TASK_STATE_REJECTED,
    TASK_STATE_WORKING,
    build_a2a_agent_message,
    build_a2a_status_update,
    ...
)
```
（`TASK_STATE_*` 与两个 build 函数加入既有 import 列表即可，其余保持不变。）

(b) `_agent_message` 改为委托纯函数（消除第二处消息形状来源），并删掉旧的 `{"type": "text"}`：

```python
def _agent_message(text: str, context_id: str) -> dict:
    """A2A ``Message``（agent 角色）。形状由纯逻辑模块单一维护，此处不再另抄一份。"""
    return build_a2a_agent_message(text=text, context_id=context_id)
```

(c) `run_published_agent_chat` 增加 `on_delta` 透传：

```python
async def run_published_agent_chat(
    db: AsyncSession,
    ctx: TenantContext,
    agent_id: UUID,
    text: str,
    *,
    conversation_id: str | None = None,
    on_delta: OnDelta | None = None,
) -> ChatResponse:
```
函数体：

```python
    return await AgentService(db, ctx).chat(
        agent_id, ChatRequest(query=text, conversation_id=conversation_id), on_delta=on_delta
    )
```
docstring 补一句：

```python
    ``on_delta`` 为真流回调（``message/stream`` 用）：逐 token 交给调用方下发；不传则
    只在返回时一次性拿到完整回答（``message/send`` 与不支持真流的路由都走这条）。
```
import 段补：`from miles_integrations.langchain.chat_models import OnDelta`。

(d) 文件末尾（`handle_a2a_rpc` 之后）新增：

```python
#: SSE 帧之间的增量队列上限。满时 ``on_delta`` 会等待消费者 —— 对上游形成背压，
#: 否则慢消费者 + 长回答会把队列撑成无界缓冲。
STREAM_QUEUE_MAXSIZE = 64

#: 与「产出一片空串」区分的收尾哨兵。
_STREAM_DONE = object()


def _sse_frame(payload: dict) -> str:
    """单个 SSE 帧。``ensure_ascii=False`` 让中文按原样出网；JSON 转义保证单行。"""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def open_a2a_stream(
    db: AsyncSession,
    ctx: TenantContext,
    agent_id: UUID,
    payload: object,
) -> dict | AsyncIterator[str]:
    """``message/stream`` 入口：前置校验失败回 JSON-RPC 错误信封，通过则回 SSE 帧迭代器。

    返回 ``dict`` 而非抛异常，是因为调用方（视图层）要据此决定**不进入 SSE**：一旦
    响应头写成 ``text/event-stream``，HTTP 状态与 Content-Type 已定，错误只能塞进帧里，
    对端解析反而更麻烦。

    不接 ``base_url``：流式帧里不含绝对地址（产物下载地址只出现在 ``tasks/get``）。
    """
    req_id: object = payload.get("id") if isinstance(payload, dict) else None
    if not isinstance(payload, dict) or "method" not in payload:
        return jsonrpc_error(req_id, INVALID_REQUEST, "非法 JSON-RPC 请求")
    params = payload.get("params")
    if not isinstance(params, dict):
        return jsonrpc_error(req_id, INVALID_PARAMS, "message/stream 缺少 params")
    try:
        await load_published_agent(db, agent_id)
        text = extract_message_text(params)
        # 未带 contextId 时生成一个：首轮就得用它，否则第一轮 checkpoint 落在别的
        # thread，对端第二轮带上该 id 时模型并无上一轮记忆。
        context_id = extract_message_context_id(params) or str(uuid4())
    except (NotFoundError, BadRequestError) as exc:
        return jsonrpc_error(req_id, INVALID_PARAMS, str(exc))
    return _stream_turn(ctx, agent_id, req_id, text, context_id)
```

(e) 接着写生成器：

```python
async def _stream_turn(
    ctx: TenantContext,
    agent_id: UUID,
    req_id: object,
    text: str,
    context_id: str,
) -> AsyncIterator[str]:
    """跑一轮对话并以 SSE 帧下发：首帧 Task、中间帧增量、末帧终态。"""
    task_id = str(uuid4())
    queue: asyncio.Queue = asyncio.Queue(maxsize=STREAM_QUEUE_MAXSIZE)
    outcome: dict = {}
    stopped = False

    async def on_delta(piece: str) -> None:
        await queue.put(piece)

    async def run_turn() -> None:
        # 自开会话：整轮对话要跨流式多次读库并在末尾 commit，依赖 get_db 依赖的
        # 回收时序不可靠（与 ws/chat._run_chat_turn 同法）。
        async with AsyncSessionLocal() as turn_db:
            try:
                outcome["response"] = await run_published_agent_chat(
                    turn_db, ctx, agent_id, text, conversation_id=context_id, on_delta=on_delta
                )
                await turn_db.commit()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                outcome["error"] = exc
                # chat() 失败时已自 commit 过失败/拦截记录，此处 rollback 只为清掉残留。
                await turn_db.rollback()
                logger.exception("A2A message/stream 执行失败: agent_id=%s", agent_id)
            finally:
                if not stopped:
                    await queue.put(_STREAM_DONE)

    turn = asyncio.create_task(run_turn())
    try:
        yield _sse_frame(
            jsonrpc_result(
                req_id,
                build_a2a_task(
                    task_id=task_id,
                    context_id=context_id,
                    state=TASK_STATE_WORKING,
                    timestamp=_now(),
                ),
            )
        )
        while True:
            item = await queue.get()
            if item is _STREAM_DONE:
                break
            yield _sse_frame(
                jsonrpc_result(
                    req_id,
                    build_a2a_status_update(
                        task_id=task_id,
                        context_id=context_id,
                        state=TASK_STATE_WORKING,
                        timestamp=_now(),
                        text=item,
                        final=False,
                    ),
                )
            )
    finally:
        # 消费端提前退出（客户端断连）：必须取消对话任务，否则 LLM 调用会跑到底白烧 token。
        # 先置 stopped 再取消：让 run_turn 的 finally 不再往无人消费的队列里塞哨兵。
        stopped = True
        if not turn.done():
            turn.cancel()

    error = outcome.get("error")
    response = outcome.get("response")
    if error is not None:
        state = TASK_STATE_REJECTED if isinstance(error, BadRequestError) else TASK_STATE_FAILED
        yield _sse_frame(
            jsonrpc_result(
                req_id,
                build_a2a_status_update(
                    task_id=task_id,
                    context_id=context_id,
                    state=state,
                    timestamp=_now(),
                    text=_failure_text(error),
                    final=True,
                ),
            )
        )
        return
    if response is None:
        # 理论不可达：哨兵与 outcome 由同一函数写入。保持显式返回而非回空帧。
        return
    job = _first_active_job(response.generative_jobs)
    if job:
        # 产物未就绪：以 working + final 收尾（final 只表示本流结束），并给出真实
        # job id —— 对端据此转向 tasks/get 轮询状态与产物。
        yield _sse_frame(
            jsonrpc_result(
                req_id,
                build_a2a_status_update(
                    task_id=task_id,
                    context_id=context_id,
                    state=TASK_STATE_WORKING,
                    timestamp=_now(),
                    text=response.answer,
                    final=True,
                    job_task_id=str(job["id"]),
                ),
            )
        )
        return
    yield _sse_frame(
        jsonrpc_result(
            req_id,
            build_a2a_status_update(
                task_id=task_id,
                context_id=context_id,
                state=TASK_STATE_COMPLETED,
                timestamp=_now(),
                text=response.answer,
                final=True,
            ),
        )
    )


def _failure_text(error: Exception) -> str:
    """失败终态给对端的可读原因：BadRequestError 的 message 本就可读，其余统一前缀。"""
    if isinstance(error, BadRequestError):
        return error.message
    return f"智能体执行失败: {error}"
```

注意：`BadRequestError` 继承 `AppError`，其 `__init__` 里 `self.message = message`
（`miles_common/exceptions.py`），所以 `error.message` 可用，不必 `getattr` 兜底。

- [ ] **Step 4: 跑测试确认通过**

```bash
cd backend && uv run python -m pytest -q tests/tenant/a2a tests/api/test_a2a_server_api.py
```
Expected: PASS。同时确认既有 `test_handle_rpc_message_send_returns_agent_message` 仍通过（`_agent_message` 委托后形状不变，只多了 `kind`）。

- [ ] **Step 5: 提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI && git add \
  backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/server.py \
  backend/tests/tenant/a2a/test_a2a_server_card.py && git commit -F - <<'EOF'
feat(a2a): 用例层实现 message/stream 的 SSE 帧编排

后台任务跑对话、有界队列承接增量，满时对上游形成背压；客户端断连即取消
对话任务，避免 LLM 调用跑到底白烧 token。会话在生成器内自开，不再依赖
get_db 的回收时序。前置失败仍回普通 JSON —— 流一旦开始就只能从帧里报错。

合规拦截回 rejected 而非 failed：前者语义是「拒绝处理该任务」，后者留给
真正的执行失败。
EOF
```

---

### Task 5: 视图层方法分流与 SSE 响应

**Files:**
- Modify: `backend/packages/miles-openapi/src/miles_openapi/views/a2a_server.py`
- Test: `backend/tests/api/test_a2a_server_api.py`

**Interfaces:**
- Consumes: Task 4 的 `open_a2a_stream(db, ctx, agent_id, payload) -> dict | AsyncIterator[str]`
- Produces: `POST /api/v1/open/a2a/agents/{agent_id}` 在 `method == "message/stream"` 时返回 `text/event-stream`

- [ ] **Step 1: 写失败测试**

`backend/tests/api/test_a2a_server_api.py` 顶部补 `import json`，并在文件末尾追加：

```python
@pytest.mark.asyncio
async def test_stream_method_returns_event_stream(as_a2a, api_client, monkeypatch):
    """message/stream 走 SSE：同一端点按 method 分流，响应体逐帧为 JSON-RPC 信封。"""
    seen: dict = {}

    async def fake_stream(_db, _ctx, _agent_id, payload):  # noqa: ANN001
        seen["method"] = payload["method"]
        seen["agent_id"] = _agent_id

        async def frames():
            yield 'data: {"jsonrpc": "2.0", "id": 1, "result": {"kind": "task"}}\n\n'
            yield 'data: {"jsonrpc": "2.0", "id": 1, "result": {"kind": "status-update", "final": true}}\n\n'

        return frames()

    monkeypatch.setattr(view_mod, "open_a2a_stream", fake_stream)

    resp = await api_client.post(RPC_PATH, json={"jsonrpc": "2.0", "id": 1, "method": "message/stream", "params": {}})

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    data_lines = [line for line in resp.text.splitlines() if line.startswith("data: ")]
    assert len(data_lines) == 2
    assert json.loads(data_lines[0][len("data: ") :])["result"]["kind"] == "task"
    assert seen["method"] == "message/stream"
    assert seen["agent_id"] == AGENT_ID


@pytest.mark.asyncio
async def test_stream_preflight_error_keeps_json_content_type(as_a2a, api_client, monkeypatch):
    """前置失败不进 SSE：错误以普通 JSON + JSON-RPC 信封返回，对端才好报错。"""
    async def fake_stream(*_args, **_kwargs):  # noqa: ANN002, ANN003
        return {"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": "A2A Server 不存在或未发布"}}

    monkeypatch.setattr(view_mod, "open_a2a_stream", fake_stream)

    resp = await api_client.post(RPC_PATH, json={"jsonrpc": "2.0", "id": 1, "method": "message/stream", "params": {}})

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.json()["error"]["code"] == -32602
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && uv run python -m pytest -q tests/api/test_a2a_server_api.py
```
Expected: FAIL —— `AttributeError: module ... has no attribute 'open_a2a_stream'`。

- [ ] **Step 3: 实现**

`a2a_server.py`：

(a) import 段补 `StreamingResponse`、`open_a2a_stream`：

```python
from fastapi.responses import JSONResponse, RedirectResponse, Response, StreamingResponse
```
```python
from miles_portal.tenant.a2a.services.server import (
    build_agent_card_by_id,
    handle_a2a_rpc,
    open_a2a_stream,
    read_task_artifact,
    resolve_default_published_agent_id,
)
```

(b) 模块级常量（放在 `router = APIRouter()` 之前）：

```python
#: SSE 响应头。``X-Accel-Buffering: no`` 关掉 Nginx 侧缓冲，否则帧会被攒到最后一起发。
_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}
```

(c) `a2a_jsonrpc` 改为按 method 分流；**返回类型标注必须是 `Response`**（`StreamingResponse` 与
`JSONResponse` 都是其子类，FastAPI 对 `Response` 不做 response model 推断，openapi 快照才不会变）：

```python
@router.post("/a2a/agents/{agent_id}")
async def a2a_jsonrpc(
    agent_id: UUID,
    request: Request,
    ctx: TenantContext = Depends(require_agent_api_key),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """A2A JSON-RPC 端点（``message/send`` / ``message/stream`` / ``tasks/*``）。

    ``message/stream`` 按 A2A 约定走 SSE，与其它方法共用同一 URL；请求体非 JSON 时回
    -32700 信封。前置校验失败的流式请求回普通 JSON，不进入 SSE。
    """
    try:
        payload = await request.json()
    except ValueError:
        return JSONResponse(jsonrpc_error(None, PARSE_ERROR, "请求体不是合法 JSON"))
    base_url = str(request.base_url)
    if isinstance(payload, dict) and payload.get("method") == "message/stream":
        opened = await open_a2a_stream(db, ctx, agent_id, payload)
        if isinstance(opened, dict):
            return JSONResponse(opened)
        return StreamingResponse(opened, media_type="text/event-stream", headers=_SSE_HEADERS)
    return JSONResponse(await handle_a2a_rpc(db, ctx, agent_id, payload, base_url=base_url))
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd backend && uv run python -m pytest -q tests/api/test_a2a_server_api.py
```
Expected: PASS。既有 `test_rpc_endpoint_returns_jsonrpc_envelope` / `test_rpc_endpoint_passes_request_base_url`
（mock `handle_a2a_rpc`，method 非 stream）与 parse-error 用例仍通过。

- [ ] **Step 5: 确认 openapi 快照未变**

```bash
make openapi-check
```
Expected: PASS（无差异）。若报差异，检查 `a2a_jsonrpc` 的返回标注是否被写成了联合类型（须是 `Response`）。

- [ ] **Step 6: 提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI && git add \
  backend/packages/miles-openapi/src/miles_openapi/views/a2a_server.py \
  backend/tests/api/test_a2a_server_api.py && git commit -F - <<'EOF'
feat(a2a): JSON-RPC 端点按 method 分流支持 message/stream

message/stream 与其余方法共用同一 URL（A2A 约定），故在视图层按 method 分流，
仅该方法返回 SSE。返回类型标注为 Response 而非联合类型：后者会触发 FastAPI
的 response model 推断，把 OpenAPI 快照改掉。
EOF
```

---

### Task 6: 文档同步

**Files:**
- Modify: `docs/guides/a2a.md`
- Modify: `docs/features/a2a-interconnect.md`
- Modify: `docs/architecture/technical-design.md`

**Interfaces:**
- Consumes: Task 1–5 的最终行为
- Produces: 文档与实现一致

- [ ] **Step 1: 改 `docs/guides/a2a.md`**

(a) 方法表补 `message/stream`：

```markdown
| `message/stream` | 流式对话（`Content-Type: text/event-stream`）。首帧 `Task(working)`，中间帧 `status-update` 携增量文本，末帧 `status-update` 带 `final=true` 与完整回答 |
```

(b) 删除「`message/stream`、`tasks/resubscribe`、`tasks/pushNotificationConfig/*` 未实现，一律回 `-32601`」这句里的 `message/stream`，改为：

```markdown
`tasks/resubscribe`、`tasks/pushNotificationConfig/*` 未实现，一律回 `-32601`（不静默成功）。
```

(c) 把「`capabilities.streaming=false`，故不支持 `message/stream`」改为：

```markdown
Card 的 `capabilities.streaming=true`：`direct_llm` / `rag` 路由逐 token 下发，`tool_agent` / `flow` /
子智能体 / `a2a_augmented` 等尚未接 `on_delta` 的路由只在末帧一次性给完整回答（对端渲染方式一致，
差别只在是否逐字到达）。
```

(d) 新增一段流式语义（放在多轮上下文段落之后）：

```markdown
**流式语义（`message/stream`）：** 事件为 A2A v0.3 形状，每帧是完整 JSON-RPC 成功信封，`result` 依次是
`Task` → `status-update`（`final=false`，`status.message.parts[].text` 为本片增量）→
`status-update`（`final=true`，`status.message` 带完整回答）。`final=true` 只表示本流结束、不等于任务终态。
流式任务的 `taskId` 是合成的、不落库：`final=true` 已给出终态，之后无需再 `tasks/get`（该 id 会回 `-32001`）。
本轮若产生异步生成任务，末帧以 `working` + `final=true` 收尾，并在 `status.message.metadata.a2aJobTaskId`
给出真实 job id —— 对端据此转向 `tasks/get` 轮询状态与产物。合规拦截以 `rejected` 收尾（拒绝处理），
其余执行失败以 `failed` 收尾；与工作台 WS 一致，token 先出网、出站合规事后扫，命中拦截时已出网内容不可追回。
```

(e) 「待做」段更新：

```markdown
- `tasks/resubscribe` 与 `tasks/pushNotificationConfig/*`（现回方法未找到）
- 多模态入站：`parts` 的 `file` / `data` 类型（现仅取 `text`）
- A2A 专用审计维度（现复用通用访问日志与限流中间件）
- A2A v1.0 迁移：PascalCase 方法名、去 `kind` 换成员名包装、`TASK_STATE_*` 取值
```

(f) 若文中出现 `protocolVersion` 为 1.0 的描述，改为 0.3；并说明「方法名与线格式均为 v0.3，故声明 0.3」。

- [ ] **Step 2: 改 `docs/features/a2a-interconnect.md`**

(a) 状态行改为：

```markdown
**状态：** 已实现（登记/引用/宿主 ✅；对外暴露 Card + `message/send` + `message/stream` 流式 + `contextId` 多轮 + `tasks/*` + 产物下载 ✅）
```

(b) 「明确不做」段把 `message/stream 真流式（Card 声明 streaming=false）` 整行删掉，替换为：

```markdown
- `tasks/resubscribe`、`tasks/pushNotificationConfig/*`（现回方法未找到）
- A2A v1.0 迁移（PascalCase 方法名 + 去 kind + `TASK_STATE_*` 取值）
- A2A 专用审计/限流（复用通用能力）
```

(c) 协议清单里补 `message/stream` 一行，并在「多轮」条目后补流式条目：「`message/stream`：SSE；首帧 `Task(working)`、中间帧 `status-update` 增量、末帧 `status-update(final=true)` 带完整回答；合成 taskId 不落库，生成任务 id 经 `status.message.metadata.a2aJobTaskId` 给出；合规拦截 `rejected`、执行失败 `failed`。」

- [ ] **Step 3: 改 `docs/architecture/technical-design.md`**

把 A2A 那一行里的「`message/stream`、`tasks/resubscribe`、`pushNotificationConfig/*` 待做」改为
「`message/stream` 流式 ✅；`tasks/resubscribe`、`pushNotificationConfig/*` 待做」，并保留指向 `a2a.md` 的链接。

- [ ] **Step 4: 提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI && git add docs/guides/a2a.md docs/features/a2a-interconnect.md docs/architecture/technical-design.md && git commit -F - <<'EOF'
docs(a2a): 同步 message/stream 与 0.3 声明

补流式语义（帧序列、合成 taskId 不需再查、生成任务 id 经 metadata 交接、
合规拦截回 rejected）与待做清单，避免文档仍写着「streaming=false」。
EOF
```

---

### Task 7: 全量质量门

**Files:** 无（仅验证）

- [ ] **Step 1: 跑全量门禁**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI && make lint-backend format-check-backend layers-check openapi-check test-backend
```
Expected: 全部 PASS（`test-backend` 全绿，此前基线为 1322 passed）。

- [ ] **Step 2: 若有失败，按类型定位**

- `layers-check` 失败 → 确认纯逻辑模块 `a2a/server.py` 未 import ORM / DB（`uuid4` 属标准库，允许）。
- `openapi-check` 失败 → 检查 `a2a_jsonrpc` 返回标注是否为 `Response`。
- `format-check-backend` 失败 → `make format-backend` 后重新提交。
- 测试失败 → 优先看 SSE 帧断言是否用了 `content-type` 精确相等（实际含 `; charset=utf-8`）。

- [ ] **Step 3: 提交（仅在 Step 1 有修复时）**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI && git add -A && git commit -F - <<'EOF'
chore(a2a): 修整全量质量门残留

格式/分层/快照三类门禁在实现提交里未一并跑满，补齐后再合并。
EOF
```

---

## 交付验收（对照 spec §4）

| spec 要求 | 覆盖任务 |
|---|---|
| Card `protocolVersion == "0.3"`、`capabilities.streaming == True` | Task 1 测试 + Task 6 文档 |
| Part 判别键统一为 `kind`（入站保持兼容） | Task 1（纯逻辑）+ Task 2（出站）+ Task 4（`_agent_message` 委托） |
| `build_a2a_status_update` 帧形状（增量 / final 带全文 / metadata / 无文本终态） | Task 3 |
| `open_a2a_stream` 前置失败回 JSON 信封（未发布 / parts 非法 / 缺 params） | Task 4 |
| 真流路由：首帧 Task + 多帧增量 + 末帧 completed 带全文 | Task 4 |
| 非真流路由：仅首帧 Task + 末帧带全文 | Task 4 |
| 输入合规拦截 → `rejected`；执行异常 → `failed` | Task 4 |
| 生成任务 → 末帧 `working/final=true` + `metadata.a2aJobTaskId` | Task 4 |
| 视图层 `text/event-stream`、前置失败保持 `application/json` | Task 5 |
| `message/send` / `tasks/*` 回归不变 | Task 4 Step 4 + Task 5 Step 4 |
| openapi 快照不变 | Task 5 Step 5 + Task 7 |
| 三份文档同步 | Task 6 |

## 明确不做（勿顺手扩范围）

- `tasks/resubscribe`、`tasks/pushNotificationConfig/*`
- A2A v1.0 迁移（PascalCase 方法名 / 去 `kind` / `TASK_STATE_*`）
- Card 界面字段名 0.3 化（`additionalInterfaces` / `transport`）—— 本批未做，后续单独一批已补上
- 多模态入站 parts、非真流路由的逐 token 化、A2A 专用审计与限流
- `MessageSendParams.configuration`（`blocking` 等）的语义
