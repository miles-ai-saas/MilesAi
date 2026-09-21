# A2A `tasks/*` 任务寻址租户边界收口 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 A2A 对外面所有「取该智能体自己的任务」的路径在遇到外租户 id 时统一回 `-32001` / 404 并留痕，而不是逸出成平台信封的 HTTP 403。

**Architecture:** 收口点选在唯一共用瓶颈 `a2a/services/server.py::load_owned_agent_task` —— 把下层 `get_generative_job_for_tenant` 抛出的 `ForbiddenError`（`assert_tenant_access` 对非超管访问外租户资源所为）归一为 `NotFoundError`，使该函数兑现它 docstring 里已有的「不存在或不属于它一律 `NotFoundError`」承诺。由此四个调用点（`tasks/get`、`tasks/cancel`、产物下载、`tasks/resubscribe`）自动口径一致，上一批为 `tasks/resubscribe` 单独加的 `except ForbiddenError` 随之成为不可达代码并被删除。

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy async / pytest + pytest-asyncio / ruff / import-linter（`make layers-check`）。

## Global Constraints

- **权威口径**：`docs/superpowers/specs/2026-09-20-a2a-task-lookup-tenant-boundary-design.md`。本计划与它冲突时以它为准；发现冲突要报告，不要擅自改设计。
- **对外错误码**：`TASK_NOT_FOUND = -32001`、`INVALID_PARAMS = -32602`、`INTERNAL_ERROR = -32603`（`tenant/a2a/server.py:41-44`）。**不要**发明新错误码。
- **协议契约**：A2A JSON-RPC 端点的协议级错误一律 **HTTP 200 + JSON-RPC 信封**（`{"jsonrpc":"2.0","id":…,"error":{"code":…,"message":…}}`），**不得**回平台信封 `{code,message,data,trace_id}`。
- **文案规则**：对外文案固定为 `"生成任务不存在"`，**不得**回显 `ForbiddenError` 的内部措辞（如「无权访问该租户资源」）。异常用 `raise … from None` 转抛，不串联上下文。
- **审计规则**：`detail` 只含元数据，**绝不**含消息正文（`aud_logs` 是租户可见面）。
- **不改动**：`get_generative_job_for_tenant` 本身（它对 workbench 等内部调用方需要保留 403）；鉴权依赖 `deps_api_auth`（401/403 是 HTTP 层认证语义）；`handle_a2a_rpc` 不加通用 `AppError` 兜底（设计 §5 明确不做）。
- **质量门（五道，全绿才提交）**：`cd backend && uv run python -m pytest -q`、`uv run ruff check .`、`uv run ruff format --check .`、`cd .. && make layers-check`、`make openapi-check`。
- **测试不得连真库**：审计走 `AsyncSessionLocal`（自开会话），单测必须用既有替身 fixture 拦掉。

---

## File Structure

| 文件 | 职责 | 本批动作 |
|---|---|---|
| `backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/server.py` | A2A 用例层：对外寻址、JSON-RPC 分发、审计 | 修改：`load_owned_agent_task` 收口；import 增 `ForbiddenError` |
| `backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/subscription.py` | `tasks/resubscribe` 订阅用例层 | 修改：删除失效的 `except ForbiddenError` 分支与 import |
| `backend/tests/tenant/a2a/test_a2a_server_card.py` | 服务层单测（已有 fake `_Db` / `_job` / autouse 审计记录器） | 修改：新增 4 条用例 |
| `backend/tests/api/test_a2a_server_api.py` | HTTP 面测试 | 修改：新增 1 条跨层组合用例 |
| `docs/guides/a2a.md` | 对外对接指南 | 修改：任务归属段补「跨租户同样收敛」 |

---

### Task 1: 在共用瓶颈收口跨租户 403

**Files:**
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/server.py`（import 行 32；`load_owned_agent_task` 函数体 281 行）
- Test: `backend/tests/tenant/a2a/test_a2a_server_card.py`（在 `# --- 5. 产物下载归属校验` 之前插入新小节）

**Interfaces:**
- Consumes: `miles_common.exceptions.ForbiddenError`（新增 import）、既有 `get_generative_job_for_tenant`（签名不变，仍可能抛 `NotFoundError` / `ForbiddenError`）。
- Produces: `load_owned_agent_task(db, ctx, agent_id, task_id) -> GenerativeJob` 的对外异常契约变为**只有** `NotFoundError`（不含任何来自租户校验的 `ForbiddenError`）。后续 Task 2/3 依赖这一契约。

- [ ] **Step 1: 写 4 条失败用例**

打开 `backend/tests/tenant/a2a/test_a2a_server_card.py`。

先改 import（第 25 行）：

```python
from miles_common.exceptions import BadRequestError, ForbiddenError, NotFoundError
```

再在 `# --- 5. 产物下载归属校验 ------------------------------------------------------` 这一行**之前**插入以下整段：

```python
# --- 4.1 任务寻址的租户边界归一（跨租户 403 → 对外 404） ---------------------- #


def _foreign_tenant_getter(message: str = "无权访问该租户资源"):  # noqa: ANN202
    """把 ``get_generative_job_for_tenant`` 换成「抛外租户 403」的替身。

    真实实现是 ``db.get`` → ``assert_tenant_access(ctx, job.tenant_id)``，后者的
    ``ForbiddenError`` 只在**非超管访问外租户资源**时抛出。
    """

    async def _get(_db, _ctx, _job_id):  # noqa: ANN001
        raise ForbiddenError(message)

    return _get


@pytest.mark.asyncio
async def test_load_owned_agent_task_normalizes_foreign_tenant_to_not_found(monkeypatch):  # noqa: ANN001
    """瓶颈处把外租户 403 归一为 ``NotFoundError``，兑现本函数 docstring 的既有承诺。

    403 逸出会同时打破两条对外契约：对端拿到平台信封（无从把错误对回自己的 ``id``），
    且 403 与 ``-32001`` 可区分 —— 等于给出探测「该 UUID 是否存在于别的租户」的 oracle。
    """
    monkeypatch.setattr(server_svc, "get_generative_job_for_tenant", _foreign_tenant_getter())

    with pytest.raises(NotFoundError) as exc:
        await server_svc.load_owned_agent_task(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, uuid4())

    # 固定文案：不把「无权访问该租户资源」这类内部措辞回显给对端
    assert "租户" not in str(exc.value)


@pytest.mark.asyncio
async def test_tasks_get_normalizes_foreign_tenant_as_task_not_found(monkeypatch, a2a_audit_recorder):  # noqa: ANN001
    """``tasks/get`` 外租户 id：JSON-RPC ``-32001``，而不是平台信封 403。"""
    monkeypatch.setattr(server_svc, "get_generative_job_for_tenant", _foreign_tenant_getter())
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tasks/get", "params": {"id": str(uuid4())}}

    envelope = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, payload, base_url=BASE)

    assert "result" not in envelope
    assert envelope["error"]["code"] == server_mod.TASK_NOT_FOUND
    # 附带收益：兜底留痕不再把外租户探测误记成「服务端内部错误」
    assert a2a_audit_recorder[0]["detail"]["errorCode"] == server_mod.TASK_NOT_FOUND


@pytest.mark.asyncio
async def test_tasks_cancel_normalizes_foreign_tenant_as_task_not_found(monkeypatch):  # noqa: ANN001
    """``tasks/cancel`` 外租户 id：与 ``tasks/get`` 同口径。"""
    monkeypatch.setattr(server_svc, "get_generative_job_for_tenant", _foreign_tenant_getter())
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tasks/cancel", "params": {"id": str(uuid4())}}

    envelope = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, payload, base_url=BASE)

    assert envelope["error"]["code"] == server_mod.TASK_NOT_FOUND


@pytest.mark.asyncio
async def test_read_task_artifact_normalizes_foreign_tenant_and_audits(monkeypatch, a2a_audit_recorder):  # noqa: ANN001
    """产物下载外租户 id：抛 ``NotFoundError``（视图回 404）**且**留一条失败流水。

    修复前 ``ForbiddenError`` 会逸出本函数，而它的 ``except NotFoundError`` 分支不覆盖
    403 —— 于是这条探测式调用在审计页上零痕迹。
    """
    monkeypatch.setattr(server_svc, "get_generative_job_for_tenant", _foreign_tenant_getter())

    with pytest.raises(NotFoundError):
        await server_svc.read_task_artifact(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, uuid4(), uuid4())

    assert len(a2a_audit_recorder) == 1
    assert a2a_audit_recorder[0]["action"] == server_mod.AUDIT_ACTION_ARTIFACT_DOWNLOAD
    assert a2a_audit_recorder[0]["outcome"] == server_mod.AUDIT_OUTCOME_FAILED
    assert a2a_audit_recorder[0]["detail"]["errorCode"] == server_mod.TASK_NOT_FOUND


```

- [ ] **Step 2: 跑用例确认 RED**

```bash
cd backend && uv run python -m pytest -q tests/tenant/a2a/test_a2a_server_card.py -k "foreign_tenant" 2>&1 | tail -20
```

预期：4 条全 FAIL。前 3 条因 `ForbiddenError` 逸出而报错（`tasks/get` / `tasks/cancel` 那两条的报错信息就是 `ForbiddenError: 无权访问该租户资源`）；第 4 条同样因 `ForbiddenError` 逸出而在 `pytest.raises(NotFoundError)` 处报错。

**若这 4 条直接通过**，说明 `ForbiddenError` 已被某处提前拦掉 —— 停下来核对这里列出的 4 行是否真的是改动前的代码，不要继续。

- [ ] **Step 3: 实现收口**

改 `backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/server.py`。

第 32 行的 import：

```python
from miles_common.exceptions import BadRequestError, ForbiddenError, NotFoundError
```

`load_owned_agent_task` 函数体（当前 281 行起的两行）改为：

```python
    try:
        job = await get_generative_job_for_tenant(db, ctx, task_id)
    except ForbiddenError:
        # 外租户 id：下层 ``assert_tenant_access`` 抛 403。若让它逸出，对端会拿到平台信封的
        # HTTP 403 —— 既破坏本端点「协议级错误一律回 JSON-RPC 信封」的契约（对端无从把错误
        # 对回自己的 ``id``），又让 403 与 ``-32001`` 可区分，等于给出探测「该任务是否存在于
        # 别的租户」的 oracle。故与「不属于本智能体」同口径归一；文案固定，不回显内部措辞。
        raise NotFoundError("生成任务不存在") from None
    if job.source_ref_type != "agent" or job.source_ref_id != agent_id:
        raise NotFoundError("生成任务不存在")
    return job
```

同时把该函数的 docstring 补一句，说明它还负责把下层的租户 403 归一为对外 404（承诺与实现的对应关系要写在承诺旁边）：

```python
    """取「该智能体自己发起」的生成任务；不存在或不属于它一律 ``NotFoundError``。

    必须校验归属：只按租户取数会让同租户另一个智能体的 key 也能查/取消本智能体任务，
    并据 ``task_id`` 推断其产物下载地址。回 404 而非 403 —— 不向对端确认任务是否存在。

    外租户 id 由下层 ``get_generative_job_for_tenant`` 的 ``ForbiddenError`` 表达，此处
    一并归一为 ``NotFoundError``：A2A 对外面不接受以 403 区分「存在但越权」与「不存在」。
    """
```

- [ ] **Step 4: 跑用例确认 GREEN**

```bash
cd backend && uv run python -m pytest -q tests/tenant/a2a/test_a2a_server_card.py 2>&1 | tail -5
```

预期：全绿（含新增 4 条）。

- [ ] **Step 5: 确认既有任务生命周期用例未被影响**

```bash
cd backend && uv run python -m pytest -q tests/tenant/a2a/test_a2a_server_card.py -k "tasks_get or tasks_cancel or artifact" 2>&1 | tail -5
```

预期：全绿 —— 同租户·跨智能体仍回 `TASK_NOT_FOUND`，成功路径仍带产物地址，产物归属校验仍 `NotFoundError`。

- [ ] **Step 6: 提交**

```bash
git add backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/server.py \
        backend/tests/tenant/a2a/test_a2a_server_card.py
git commit -F - <<'EOF'
fix(a2a): 任务寻址在瓶颈处收敛跨租户 403

load_owned_agent_task 已承诺「不存在或不属于它一律 NotFoundError」，但它先经
get_generative_job_for_tenant 做租户校验，外租户 id 会在那一层抛 ForbiddenError ——
承诺落空，四个调用点后果还不一致：tasks/get 与 tasks/cancel 回平台信封的 HTTP 403
（对端无从把错误对回自己的 id，且 403 与 -32001 可区分，等于存在性 oracle），
产物下载连审计都没有。

改为在瓶颈处把 ForbiddenError 归一为 NotFoundError，四个调用点一次对齐，
审计的 errorCode 也从误标的 -32603 纠正为 -32001。
EOF
```

---

### Task 2: 删除 `open_task_subscription` 里失效的 403 分支

**Files:**
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/subscription.py`（import 行 21；`try/except` 块 126-132 行）

**Interfaces:**
- Consumes: Task 1 建立的契约 —— `load_owned_agent_task` 不再抛 `ForbiddenError`。
- Produces: `open_task_subscription` 的 `try/except` 只剩 `BadRequestError` 与 `NotFoundError` 两个分支；该函数行为**不变**。

- [ ] **Step 1: 记录改动前的基线**

```bash
cd backend && uv run python -m pytest -q tests/tenant/a2a/test_a2a_task_resubscribe.py 2>&1 | tail -3
```

预期：全绿。记下通过数（后续步骤要与它一致）。

- [ ] **Step 2: 删除分支与 import**

`subscription.py` 第 21 行的 import 改为（去掉 `ForbiddenError`）：

```python
from miles_common.exceptions import BadRequestError, NotFoundError
```

`open_task_subscription` 里删掉整个 `except ForbiddenError:` 块（当前 126-132 行），使其紧接 `except NotFoundError` 之后就是 `# 结束请求级事务并归还连接…` 那段注释。删后的 `try/except` 应为：

```python
    try:
        job_id = parse_task_id(params)
        job = await load_owned_agent_task(db, ctx, agent_id, job_id)
    except BadRequestError as exc:
        await _audit_failure(ctx, agent_id, INVALID_PARAMS, started)
        return jsonrpc_error(req_id, INVALID_PARAMS, str(exc))
    except NotFoundError as exc:
        # 不区分「不存在 / 不属于该智能体 / 是合成的流式 id / 属于外租户」：一律按任务不存在
        # 回，不向对端确认任务是否存在。外租户那一路由 load_owned_agent_task 归一（见其注释）。
        await _audit_failure(ctx, agent_id, TASK_NOT_FOUND, started)
        return jsonrpc_error(req_id, TASK_NOT_FOUND, str(exc))
```

注意：`except NotFoundError as exc` 分支回的是 `str(exc)`，而 Task 1 已保证 `NotFoundError` 的文案是固定的 `"生成任务不存在"`，所以这里不会漏出内部措辞。

- [ ] **Step 3: 确认 `ForbiddenError` 已无残留**

```bash
cd backend && rg -n "ForbiddenError" packages/miles-portal/src/miles_portal/tenant/a2a/services/subscription.py
```

预期：无输出。

- [ ] **Step 4: 跑回归确认行为不变**

```bash
cd backend && uv run python -m pytest -q tests/tenant/a2a/test_a2a_task_resubscribe.py 2>&1 | tail -3
```

预期：全绿，通过数与 Step 1 一致。

其中 `test_preflight_rejects_foreign_tenant_task_without_leaking_existence` 是**主判别器**：它注入的 `ForbiddenError` 现在由 Task 1 的瓶颈转换承担，若有人日后移除那个 `try/except`，这条用例会变红。

- [ ] **Step 5: 提交**

```bash
git add backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/subscription.py
git commit -F - <<'EOF'
refactor(a2a): 删除订阅里失效的跨租户 403 分支

收口已下沉到 load_owned_agent_task，该分支的唯一异常来源在那里就被转换，
留着即是不可达代码，且会让「外租户一律 -32001」这个不变式出现两处真相。

其注释里「403 与 -32001 可区分等于存在性 oracle」的理由已上移到瓶颈处。
EOF
```

---

### Task 3: HTTP 面组合用例（真实前置校验 → 真实信封 → 真实状态码）

**Files:**
- Modify: `backend/tests/api/test_a2a_server_api.py`（在 `test_resubscribe_rate_limited_before_sse` 之前插入）
- Test: 同文件

**Interfaces:**
- Consumes: Task 1 的收口；既有 fixture `as_a2a`（覆盖 `require_agent_api_key` 并返回 `api_app`）、`api_client`。
- Produces: 一条把「服务层返回 JSON-RPC 信封」与「HTTP 状态码 / Content-Type」同时钉住的用例 —— 服务层单测看不到状态码，这道缝只能在这一层锁。

- [ ] **Step 1: 写失败用例**

在 `backend/tests/api/test_a2a_server_api.py` 的 `async def test_resubscribe_rate_limited_before_sse(` **之前**插入：

```python
@pytest.mark.asyncio
async def test_tasks_get_foreign_tenant_returns_jsonrpc_not_platform_envelope(as_a2a, api_client, monkeypatch):
    """外租户 id 必须收敛为 HTTP 200 + JSON-RPC ``-32001``，而不是平台信封的 403。

    服务层单测直接 ``await handle_a2a_rpc``，看不到 HTTP 状态码与 Content-Type —— 而本缺陷
    的可观测面恰在两者之间（协议契约要求 HTTP 200 + JSON-RPC 正文）。这里只替换 I/O 出口
    （取任务 = 抛外租户 403、审计 = 记录），其余全真，让请求经 ASGI 走完一次分发。
    """
    agent = Agent()
    agent.id = AGENT_ID
    agent.agent_type = AgentType.CUSTOM
    agent.status = AgentStatus.ENABLED
    agent.config = {A2A_PUBLISH_FLAG: True}
    agent.deleted_at = None

    class _Db:
        """最小 DB 替身：本路径只用到 ``get``（取智能体）。"""

        async def get(self, _model, _id):  # noqa: ANN001
            return agent

        async def commit(self):  # noqa: ANN201
            pass

    async def override_db():  # noqa: ANN202
        yield _Db()

    async def _foreign(_db, _ctx, _job_id):  # noqa: ANN001
        raise ForbiddenError("无权访问该租户资源")

    recorded: list[dict] = []

    async def _write(**kwargs):  # noqa: ANN003
        recorded.append(kwargs)

    as_a2a.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(a2a_svc, "get_generative_job_for_tenant", _foreign)
    monkeypatch.setattr(a2a_svc, "write_a2a_audit", _write)

    resp = await api_client.post(
        RPC_PATH,
        json={"jsonrpc": "2.0", "id": 5, "method": "tasks/get", "params": {"id": str(uuid4())}},
    )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    body = resp.json()
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == 5
    assert body["error"]["code"] == -32001
    # 平台信封的指纹是这几个键：出现即说明 403 逸出到了全局处理器
    assert "trace_id" not in body
    # 探测式调用必须留痕，且错误码不再是兜底路径误标的 -32603
    assert len(recorded) == 1
    assert recorded[0]["outcome"] == "failed"
    assert recorded[0]["detail"]["errorCode"] == -32001
```

- [ ] **Step 2: 补 import**

该文件其余所需符号（`Agent` / `AgentStatus` / `AgentType` / `A2A_PUBLISH_FLAG` / `get_db` / `a2a_svc` / `audit_svc`）已在既有 import 区中，**只需**把异常那一行补上 `ForbiddenError`：

```python
from miles_common.exceptions import ForbiddenError, NotFoundError
```

- [ ] **Step 3: 跑用例确认 GREEN**

```bash
cd backend && uv run python -m pytest -q tests/api/test_a2a_server_api.py::test_tasks_get_foreign_tenant_returns_jsonrpc_not_platform_envelope 2>&1 | tail -5
```

预期：PASS。

- [ ] **Step 4: 证伪 —— 确认这条用例真的能抓到回归**

临时把 Task 1 的收口撤掉，跑这条用例，确认它变红，再恢复。**注意不能用 `git stash`**：Task 1 已经 commit 了，stash 只捕获未提交改动，会打印 `No local changes to save` 然后给你一个**假绿**。要按 commit 回退：

```bash
git checkout 7110ee7e^ -- backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/server.py
cd backend && uv run python -m pytest -q tests/api/test_a2a_server_api.py::test_tasks_get_foreign_tenant_returns_jsonrpc_not_platform_envelope 2>&1 | tail -8
cd .. && git checkout HEAD -- backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/server.py
```

预期：撤掉收口后 **FAIL**，断言失败在 `resp.status_code == 200`（实际是 403），并伴随一条 `POST … 403` 的 access log。恢复后 `git diff` 应为空，重新跑一次为 PASS。

**若撤掉收口后仍然 PASS**，说明这条用例没有判别力（例如被 `as_a2a` 的某个 override 短路了）—— 停下来查明原因，不要带着假通过的用例提交。

- [ ] **Step 5: 确认工作树已恢复**

```bash
git status --porcelain
```

预期：只剩 `backend/tests/api/test_a2a_server_api.py` 一个 ` M`。

- [ ] **Step 6: 提交**

```bash
git add backend/tests/api/test_a2a_server_api.py
git commit -F - <<'EOF'
test(a2a): 锁住外租户 id 在 HTTP 面的收敛形状

服务层单测看不到状态码与 Content-Type，而本次缺陷的可观测面恰在「服务层返回信封」与
「HTTP 响应」之间。新增一条只替换 I/O 出口的用例，让请求经 ASGI 走完真实分发，
同时钉住 HTTP 200、JSON-RPC -32001、无平台信封 trace_id、以及探测必留痕。

已用撤掉收口的方式验证过它是 RED。
EOF
```

---

### Task 4: 文档同步与全量质量门

**Files:**
- Modify: `docs/guides/a2a.md`（任务归属段）
- Test: 无（本任务只改文档 + 跑门）

**Interfaces:**
- Consumes: Task 1-3 的最终行为。
- Produces: 对外文档与实现一致；五道质量门全绿的证据。

- [ ] **Step 1: 更新任务归属段**

`docs/guides/a2a.md` 当前该段为：

> 任务归属：`tasks/get` / `tasks/cancel` / 产物下载都校验「该任务由本智能体发起」（job 的 `source_ref_type=agent` + `source_ref_id=agent_id`），不属于则回 404 / `-32001` 而非 403 —— 不向对端确认任务是否存在。若只按租户校验，同租户另一个智能体的 key 就能查/取消本智能体任务并猜到其产物地址。

改为（在句末补两种「不属于」的区分与端点形态差异）：

> 任务归属：`tasks/get` / `tasks/cancel` / `tasks/resubscribe` / 产物下载都校验「该任务由本智能体发起」（job 的 `source_ref_type=agent` + `source_ref_id=agent_id`），不属于则回 `-32001` / 404 而非 403 —— 不向对端确认任务是否存在。「不属于」含两种情形，对端**无从区分**：同租户另一个智能体的任务（`-32001`），以及**其他租户**的任务（同样 `-32001`，不因越租户而改成 403）。若只按租户校验，同租户另一个智能体的 key 就能查/取消本智能体任务并猜到其产物地址。产物下载是普通 HTTP 端点（非 JSON-RPC），同一语义以 **404 状态码**表达；这四种调用无论成败都会在审计流水留痕。

- [ ] **Step 2: 确认文档里没有残留的相反表述**

```bash
rg -n "403" docs/guides/a2a.md docs/features/a2a-interconnect.md
```

预期：只剩「回 404 / `-32001` 而非 403」这类**说明不这么做**的表述；若出现「越权回 403」之类与实现相反的描述，改成与上面一致。

- [ ] **Step 3: 跑五道质量门**

```bash
cd backend && uv run python -m pytest -q && uv run ruff check . && uv run ruff format --check .
cd .. && make layers-check && make openapi-check
```

预期：全绿。`pytest` 通过数应等于「Task 1 之前基线 + 5」（本批新增 4 条服务层用例 + 1 条 HTTP 用例）；`layers-check` 报 `Contracts: 7 kept, 0 broken.`；`openapi-check` 报 `OpenAPI snapshot OK`（本批不改视图签名与 docstring，快照**不应**漂移 —— 若报漂移说明误改了视图文件，停下来核对）。

- [ ] **Step 4: 检查是否触发了「无引用模块」守卫**

```bash
cd backend && uv run python -m pytest -q tests/test_no_unreferenced_modules.py 2>&1 | tail -3
```

预期：通过（本批不改模块结构，只是函数内的行为）。

- [ ] **Step 5: 提交**

```bash
git add docs/guides/a2a.md
git commit -F - <<'EOF'
docs(a2a): 任务归属段写明跨租户同样收敛为不确认存在性

原句只在「同租户跨智能体」意义上成立，跨租户会逸出成 403。补上两种「不属于」对端无从
区分、以及产物下载以 404 状态码表达同一语义。
EOF
```

---

## 完成后的验收清单

- [ ] `tasks/get` / `tasks/cancel` 外租户 id 回 HTTP 200 + JSON-RPC `-32001`
- [ ] 产物下载外租户 id 回 404 **且**留下一条 `failed` 流水
- [ ] `tasks/resubscribe` 外租户 id 行为不变（`-32001` + 留痕）
- [ ] 同租户·跨智能体、超管、未发布智能体、非法 id 四条既有路径行为不变
- [ ] `ForbiddenError` 在 `subscription.py` 中不再出现
- [ ] `get_generative_job_for_tenant`、`deps_api_auth`、`handle_a2a_rpc` 的通用兜底**均未被改动**
- [ ] 五道质量门全绿

## 已知残余（设计 §5，本批有意不处理）

1. `_handle_tasks_cancel` 第二个 `try` 里 `cancel_job` 的竞态 `NotFoundError`、以及 Redis `publish` 故障，仍会以平台信封返回（需要 `handle_a2a_rpc` 的通用 `AppError` 兜底才能覆盖，本批明确不做）。
2. `_handle_message_send` 的 `except Exception` 会把配额类 `ForbiddenError` 误标为 `-32603`（不逸出，属展示层误报）。
