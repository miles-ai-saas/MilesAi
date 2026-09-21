# A2A 对外面错误封口（`AppError` → JSON-RPC 信封）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 A2A 对外面不再把业务异常（`AppError`）逸出成平台信封或误标成 `-32603`，并把产物下载失败路径的审计补齐。

**Architecture:** 四处改动不可互相替代（设计 §4 的分工，务必按此验收）：

1. **结构兜底**（治「漏捕」）：`handle_a2a_rpc` 新增 `except AppError`，把逸出的业务异常译成 JSON-RPC 信封 —— 修 **E2**；
2. **停止截获**（治 E3 的「错捕」）：`_handle_message_send` 的 `except Exception` 加一行 `except AppError: raise`，让业务异常穿过 handler 交给兜底 —— **兜底单独存在时 E3 仍不修**；
3. **逐点补宽**（治 E1）：`read_task_artifact` 返回文件流而非 JSON-RPC，兜底覆盖不到，必须自己补 `except ForbiddenError` / `AppError` / `Exception` 并留痕；
4. **纵深防御**：视图 `a2a_jsonrpc` 的 `try/except AppError`（当前无可达逸出点，只作注入式锁定）。

映射没有唯一归属是根因：每个 `_handle_*` 记得就映射、忘了就逸出。本批让「A2A 对外面不逸出 `AppError`」成为**结构性**保证，逐点映射退化为「更精确的语义」而非唯一防线。

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy async / pytest + pytest-asyncio / ruff / import-linter（`make layers-check`）。

## Global Constraints

- **权威口径**：`docs/superpowers/specs/2026-09-21-a2a-error-sealing-design.md`。本计划与它冲突时以它为准；发现冲突要报告，不要擅自改设计。
- **对外错误码**（`miles-portal/.../tenant/a2a/server.py:38-49`，**不要发明新码**）：`PARSE_ERROR=-32700`、`INVALID_REQUEST=-32600`、`METHOD_NOT_FOUND=-32601`、`INVALID_PARAMS=-32602`、`INTERNAL_ERROR=-32603`、`RATE_LIMITED=-32000`、`TASK_NOT_FOUND=-32001`、`TASK_NOT_CANCELABLE=-32002`。
- **协议契约**：JSON-RPC 端点的协议级错误一律 **HTTP 200 + JSON-RPC 信封**（`{"jsonrpc":"2.0","id":…,"error":{"code":…,"message":…}}`），**不得**回平台信封 `{code,message,data,trace_id}`。唯一例外见「未预期异常」一条。
- **未预期异常口径不变**：非 `AppError` 仍「审计 `INTERNAL_ERROR` 后原样重抛」→ HTTP 500 平台信封。**不要**顺手改成回信封。
- **审计规则**：`detail` 只含元数据，**绝不**含消息正文（`aud_logs` 是租户可见面）。新增 `errorType`（异常类名）/`errorStatus`（HTTP status）**只记类型与状态码**，不记 `exc.message`。
- **不改动**：`AttachmentService` 的异常语义（跨租户仍抛 `ForbiddenError`，只改 docstring）；鉴权依赖 `deps_api_auth`（401/403 是 HTTP 层认证语义）；`get_generative_job_for_tenant` 本身；限流与流内错误的既有处理（`limits.py`、`audit.py` 的 fail-open，`server.py:690/:697` 与 `subscription.py:338` 的流内帧协议）。
- **`except` 顺序**：子类在前。`NotFoundError` / `ForbiddenError` / `BadRequestError` 都是 `AppError` 子类，宽分支必须排在最后。
- **`except` 块内 `raise` 新异常不会被同一 `try` 的其它 `except` 再捕获**，故不会双写审计；这是 E1 唯一容易写错的地方，用例必须钉住「恰好一条流水」。
- **既有守卫**（`backend/tests/test_no_silent_broad_except.py`）：宽泛 `except` 不得静默；宽泛 + 只记日志不重抛的日志必须带 `exc_info`（或 `logger.exception`）。本批新增的 `except AppError: raise`（有 `raise`）与 `except Exception: … raise`（重抛）都合规；**窄类型**（`AppError`/`ForbiddenError`）即使不重抛也只要求「不静默」，本批各分支都有审计调用，无需 `# 静默可接受` 标注。
- **质量门（五道，全绿才提交）**：`cd backend && uv run python -m pytest -q`、`uv run ruff check .`、`uv run ruff format --check .`、`cd .. && make layers-check`、`make openapi-check`。
- **不连真库**：审计走 `AsyncSessionLocal`（自开会话），单测必须用既有 `a2a_audit_recorder` fixture 拦掉。
- **视图层不改 `a2a_jsonrpc` 的 docstring** → `openapi-check` **不应**漂移。若实施中确需补说明，必须同批 `make openapi-update` 并更新 `backend/openapi/openapi.snapshot.json`，在提交说明里点出。

---

## File Structure

| 文件 | 职责 | 本批动作 |
|---|---|---|
| `backend/packages/miles-portal/src/miles_portal/tenant/a2a/server.py` | A2A 纯函数层（Card / 信封 / 常量） | 修改：新增 `_TASKS_METHOD_PREFIX` 常量与 `app_error_envelope`；import 增 `AppError` |
| `backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/server.py` | A2A 用例层（分发 / 审计 / 产物下载） | 修改：`handle_a2a_rpc` 加兜底、`_rpc_audit_detail` 加 `origin`、`_handle_message_send` 停止截获、`read_task_artifact` 补三档 `except` 并抽 `_audit_artifact_failure`；import 增 `AppError`、`app_error_envelope` |
| `backend/packages/miles-openapi/src/miles_openapi/views/a2a_server.py` | API 声明层（路由与 HTTP 形状） | 修改：`a2a_jsonrpc` 三处分流包进 `try/except AppError` |
| `backend/packages/miles-portal/src/miles_portal/tenant/attachments/services/attachment.py` | 附件服务 | 修改：`_get_or_raise` docstring 说真话 |
| `backend/tests/tenant/a2a/test_a2a_server_card.py` | 纯函数 + 服务层单测（已有 `_Db` / `_job` / `_artifact_job` / `a2a_audit_recorder`） | 修改：新增 4 组用例（Task 1/2/3/4） |
| `backend/tests/api/test_a2a_server_api.py` | HTTP 面测试 | 修改：新增 5 条跨层用例 |
| `docs/guides/a2a.md` | 对外对接指南 | 修改：新增「错误与信封」小节；改任务归属段、产物下载段、审计段 |
| `docs/features/a2a-interconnect.md` | 功能规格 | 修改：错误码段（执行异常不再一律 `-32603`） |
| `docs/superpowers/specs/2026-09-20-a2a-task-lookup-tenant-boundary-design.md` | 上一批设计 | 修改：§5 残余 #1 的两条标注为已关闭 |

**任务依赖**：Task 1（纯函数）→ Task 2（兜底，用 Task 1 的函数）→ Task 3/4（互不依赖）→ Task 5（HTTP 面，需 Task 2/3/4 的改动在位）→ Task 6（文档与质量门）。Task 3 与 Task 4 可按任意顺序。

---

### Task 1: 纯函数 `app_error_envelope` 与码映射表

**Files:**
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/a2a/server.py`（import 第 20 行；常量区第 38-49 行；`jsonrpc_error` 之后，第 449 行）
- Test: `backend/tests/tenant/a2a/test_a2a_server_card.py`（纯函数段 = 第 56 行 `# --- 1. 纯函数` 到第 481 行；插在 `test_rate_limited_code_is_in_implementation_defined_range`（第 400-402 行）之后）

**Interfaces:**
- Consumes: `miles_common.exceptions.AppError`（`status_code: int`、`message: str`）、既有 `jsonrpc_error`、既有常量。
- Produces: `app_error_envelope(method: str | None, req_id: object, exc: AppError) -> dict`。Task 2/3/4/5 依赖它；符号名与签名不得改。

- [ ] **Step 1: 写失败的纯函数用例**

打开 `backend/tests/tenant/a2a/test_a2a_server_card.py`。

第 24 行 import 改为（补 `ConflictError` / `UnauthorizedError`）：

```python
from miles_common.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError, UnauthorizedError
```

在 `test_rate_limited_code_is_in_implementation_defined_range`（第 402 行 `assert server_mod.RATE_LIMITED == -32000` 之后）插入整段：

```python
@pytest.mark.parametrize(
    ("method", "exc", "expected"),
    [
        # ``tasks/*`` 域：401/403/404 一律压成 -32001，以免与「任务不存在」可区分
        ("tasks/get", NotFoundError("生成任务不存在"), server_mod.TASK_NOT_FOUND),
        ("tasks/cancel", ForbiddenError("无权访问该租户资源"), server_mod.TASK_NOT_FOUND),
        ("tasks/resubscribe", UnauthorizedError("未授权"), server_mod.TASK_NOT_FOUND),
        # 其它域：401/403/404 与 400 同压 -32602（与既有逐点映射一致）
        ("message/send", BadRequestError("输入内容包含敏感词，已拦截：某词"), server_mod.INVALID_PARAMS),
        ("message/send", ForbiddenError("配额已用尽"), server_mod.INVALID_PARAMS),
        ("message/send", NotFoundError("生成任务不存在"), server_mod.INVALID_PARAMS),
        (None, BadRequestError("坏参数"), server_mod.INVALID_PARAMS),
        # ``tasks/*`` 域的 400 不受域规则影响：它本来就是「参数错」，不是存在性 oracle
        ("tasks/get", BadRequestError("id 不是合法 UUID"), server_mod.INVALID_PARAMS),
        # 其它状态（含 409）归内部错误：`INTERNAL_ERROR` 的保留语义不被稀释
        ("tasks/get", ConflictError("任务冲突"), server_mod.INTERNAL_ERROR),
        ("message/send", ConflictError("任务冲突"), server_mod.INTERNAL_ERROR),
    ],
)
def test_app_error_envelope_maps_status_and_domain(method, exc, expected):  # noqa: ANN001
    """逐格钉住映射表：域判定只对 401/403/404 生效，400 与 409 与域无关。"""
    envelope = server_mod.app_error_envelope(method, 7, exc)

    assert set(envelope) == {"jsonrpc", "id", "error"}
    assert envelope["jsonrpc"] == "2.0"
    assert envelope["id"] == 7
    assert envelope["error"]["code"] == expected
    # 文案原样透传：它是对端唯一能读到的失败原因，压缩它等于让对端无法排查
    assert envelope["error"]["message"] == str(exc)
    assert "result" not in envelope


def test_app_error_envelope_never_emits_platform_envelope():
    """对端必须能把错误对回自己的 ``id``：平台信封的四个键一个都不能出现。"""
    envelope = server_mod.app_error_envelope("message/send", None, BadRequestError("坏参数"))

    assert set(envelope) == {"jsonrpc", "id", "error"}
    assert not ({"code", "data", "trace_id", "message"} & set(envelope))
```

- [ ] **Step 2: 跑用例确认失败（RED）**

```bash
cd backend && uv run python -m pytest tests/tenant/a2a/test_a2a_server_card.py -q -k app_error_envelope
```

预期：`AttributeError: module 'miles_portal.tenant.a2a.server' has no attribute 'app_error_envelope'`（收集/执行期报错即 RED）。

- [ ] **Step 3: 实现纯函数**

在 `backend/packages/miles-portal/src/miles_portal/tenant/a2a/server.py`：

第 20 行 import 改为：

```python
from miles_common.exceptions import AppError, BadRequestError
```

在常量区（`RATE_LIMITED` 之后、`AUDIT_ACTION_*` 之前）新增：

```python
#: 归属 ``tasks/*`` 域的方法前缀。该域的 401/403/404 压成 ``TASK_NOT_FOUND``，
#: 否则跨租户任务回 ``-32602``（参数错）会与「任务不存在」可区分 —— 存在性 oracle
#: 会从另一条路放回来（上一批刚收口掉的那个问题）。
_TASKS_METHOD_PREFIX = "tasks/"
```

在 `jsonrpc_error` 之后新增：

```python
def app_error_envelope(method: str | None, req_id: object, exc: AppError) -> dict:
    """把 ``AppError`` 译成 JSON-RPC 错误信封；A2A 对外面不接受平台信封。

    逐点映射（各 ``_handle_*`` 里的 ``except``）仍是第一道，语义更精确；本函数是
    「handler 漏捕或捕得太宽」时的统一归属，保证对外形状一致。

    ``tasks/*`` 域的 401/403/404 压成 ``TASK_NOT_FOUND``：延续「对端不得获得存在性
    oracle」的不变式。其余域的权限/冲突问题压成 ``INVALID_PARAMS`` / ``INTERNAL_ERROR``，
    对端读不出真实原因 —— 这是已知取舍，由审计的 ``errorType``/``errorStatus`` 补偿。
    """
    status = exc.status_code
    if isinstance(method, str) and method.startswith(_TASKS_METHOD_PREFIX) and status in (401, 403, 404):
        code = TASK_NOT_FOUND
    elif status in (400, 401, 403, 404):
        code = INVALID_PARAMS
    else:
        code = INTERNAL_ERROR
    return jsonrpc_error(req_id, code, exc.message)
```

- [ ] **Step 4: 跑用例确认通过（GREEN）**

```bash
cd backend && uv run python -m pytest tests/tenant/a2a/test_a2a_server_card.py -q -k app_error_envelope
```

预期：`test_app_error_envelope_maps_status_and_domain` 10 条 + `test_app_error_envelope_never_emits_platform_envelope` 1 条 = 11 条全过。

- [ ] **Step 5: 全量单测确认无回归**

```bash
cd backend && uv run python -m pytest tests/tenant/a2a tests/api -q
```

预期：全绿（本步只加纯函数，不改既有行为）。

- [ ] **Step 6: 提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI && git add -A && git commit -F - <<'EOF'
feat(a2a): 新增 AppError → JSON-RPC 信封的纯映射函数

把「业务异常译成对外错误码」这件事从各 handler 的散点记忆收归一处：tasks/* 域的
401/403/404 压成 -32001（延续对端不得获得存在性 oracle 的不变式），其余域与 400
压成 -32602，409/5xx 压成 -32603。逐格参数化用例钉住映射表本身，后续接线不再靠约定。
EOF
```

---

### Task 2: `handle_a2a_rpc` 兜底与审计 `origin`（修 E2）

**Files:**
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/server.py`（import 第 25 行；纯函数 import 块第 33 行起；`handle_a2a_rpc` 第 427-475 行；`_rpc_audit_detail` 第 483-502 行）
- Test: `backend/tests/tenant/a2a/test_a2a_server_card.py`（在 `# --- 5. 产物下载归属校验`（第 1068 行）之前插入新小节；**不要**插在 `# --- 4.1`（第 943 行）之前 —— 那是上一批的用例段，别打散它）

**Interfaces:**
- Consumes: Task 1 的 `app_error_envelope(method, req_id, exc)`；`_AUDIT_ACTION_BY_METHOD`；既有 `write_a2a_audit` / `_rpc_audit_outcome` / `_rpc_audit_detail`。
- Produces: `handle_a2a_rpc` 的对外契约变为「除未预期异常外，一律回 JSON-RPC 信封（不重抛）」。`_rpc_audit_detail(payload, envelope, *, started, method, origin=None)` 新增关键字参数；`origin` 非空时 `detail` 多出 `errorType`/`errorStatus` 两键。Task 3/5 依赖这一形状。

- [ ] **Step 1: 写 3 条失败用例**

在 `backend/tests/tenant/a2a/test_a2a_server_card.py` 的 `# --- 5. 产物下载归属校验`（第 1068 行）**之前**插入整段：

```python
# --- 4.2 RPC 层兜底：漏捕的 AppError 不再逸出（治 E2 的竞态） ------------------ #


@pytest.mark.asyncio
async def test_tasks_cancel_race_maps_not_found_at_rpc_layer(monkeypatch, a2a_audit_recorder):  # noqa: ANN001
    """E2 复现：`cancel_job` 的竞态 `NotFoundError` 不再逸出成平台信封 / `-32603`。

    `_handle_tasks_cancel` 第二个 `try` 只捕 `BadRequestError`；job 在
    `load_owned_agent_task` 之后、`cancel_job` 之前被删时，`NotFoundError` 会直接逸出到
    `handle_a2a_rpc`。修复前它撞 `except Exception` → 审计 `-32603` 后重抛 → HTTP 500。
    """
    job_id = uuid4()
    owned = _job("running", job_id=job_id, agent_id=AGENT_ID)

    async def fake_get(_db, _ctx, _job_id):  # noqa: ANN001
        return owned

    class _RacedJobService:
        """模拟 load 与 cancel 之间任务消失。"""

        def __init__(self, _db, _ctx) -> None:
            pass

        async def cancel_job(self, _job_id):  # noqa: ANN001
            raise NotFoundError("生成任务不存在")

    monkeypatch.setattr(server_svc, "get_generative_job_for_tenant", fake_get)
    monkeypatch.setattr(server_svc, "GenerativeJobService", _RacedJobService)
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tasks/cancel", "params": {"id": str(job_id)}}

    envelope = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, payload, base_url=BASE)

    # 键集等值即「没有逸出到全局处理器」：平台信封是 {code,message,data,trace_id}
    assert set(envelope) == {"jsonrpc", "id", "error"}
    assert envelope["id"] == 1
    assert envelope["error"]["code"] == server_mod.TASK_NOT_FOUND
    assert len(a2a_audit_recorder) == 1
    assert a2a_audit_recorder[0]["outcome"] == server_mod.AUDIT_OUTCOME_FAILED
    assert a2a_audit_recorder[0]["detail"]["errorCode"] == server_mod.TASK_NOT_FOUND
    # 原始类型与 status 落进租户可见面：对外码被压平后，这是唯一能读出真实原因的出口
    assert a2a_audit_recorder[0]["detail"]["errorType"] == "NotFoundError"
    assert a2a_audit_recorder[0]["detail"]["errorStatus"] == 404
    assert a2a_audit_recorder[0]["detail"]["taskId"] == str(job_id)


@pytest.mark.asyncio
async def test_rpc_layer_maps_uncaptured_app_error(monkeypatch, a2a_audit_recorder):  # noqa: ANN001
    """兜底本身：把分发层换成「直接抛」的替身，模拟某个 handler 忘了逐点映射。

    **注入式用例**：当前没有可达的漏捕点（E2 已由上面那条覆盖），本用例锁的是兜底机制
    不被重构删掉，不得当作缺陷回归闸门。用例从 `_dispatch_a2a_rpc` 起替换，故「handler
    自己就漏捕」这一层也被覆盖到。
    """

    async def _boom(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise BadRequestError("参数里有个东西不合法")

    monkeypatch.setattr(server_svc, "_dispatch_a2a_rpc", _boom)
    payload = {"jsonrpc": "2.0", "id": 9, "method": "tasks/get", "params": {"id": str(uuid4())}}

    envelope = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, payload, base_url=BASE)

    assert envelope["error"]["code"] == server_mod.INVALID_PARAMS
    assert a2a_audit_recorder[0]["detail"]["errorType"] == "BadRequestError"
    assert a2a_audit_recorder[0]["detail"]["errorStatus"] == 400


@pytest.mark.asyncio
async def test_rpc_layer_still_reraises_unexpected_exception(monkeypatch, a2a_audit_recorder):  # noqa: ANN001
    """口径不变：非 `AppError` 仍原样重抛（→ HTTP 500 平台信封），且照旧留痕。

    这条是钉住设计 §3.4「不改口径」的回归闸门 —— 若有人顺手把兜底写成「一律回信封」，
    这里会立刻红。
    """
    job_id = uuid4()
    owned = _job("running", job_id=job_id, agent_id=AGENT_ID)

    async def fake_get(_db, _ctx, _job_id):  # noqa: ANN001
        return owned

    class _BoomJobService:
        def __init__(self, _db, _ctx) -> None:
            pass

        async def cancel_job(self, _job_id):  # noqa: ANN001
            raise RuntimeError("redis 不可用")

    monkeypatch.setattr(server_svc, "get_generative_job_for_tenant", fake_get)
    monkeypatch.setattr(server_svc, "GenerativeJobService", _BoomJobService)
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tasks/cancel", "params": {"id": str(job_id)}}

    with pytest.raises(RuntimeError):
        await server_svc.handle_a2a_rpc(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, payload, base_url=BASE)

    assert len(a2a_audit_recorder) == 1
    assert a2a_audit_recorder[0]["outcome"] == server_mod.AUDIT_OUTCOME_FAILED
    assert a2a_audit_recorder[0]["detail"]["errorCode"] == server_mod.INTERNAL_ERROR
    # 未预期异常不带 errorType：`detail` 的键集是对外契约的一部分，顺手加键会漂移
    assert "errorType" not in a2a_audit_recorder[0]["detail"]
```

- [ ] **Step 2: 跑用例确认失败（RED）**

```bash
cd backend && uv run python -m pytest tests/tenant/a2a/test_a2a_server_card.py -q -k "rpc_layer or race_maps"
```

预期：`test_tasks_cancel_race_maps_not_found_at_rpc_layer` 与 `test_rpc_layer_maps_uncaptured_app_error` 失败（`-32603` / 异常重抛）；`test_rpc_layer_still_reraises_unexpected_exception` 可能已经通过（它钉的是不变式）。**记下哪条红、为什么**，不要跳过。

- [ ] **Step 3: 实现兜底与审计补偿**

在 `backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/server.py`：

第 25 行 import 改为（`ForbiddenError` 已在，只补 `AppError`）：

```python
from miles_common.exceptions import AppError, BadRequestError, ForbiddenError, NotFoundError
```

纯函数 import 块（第 33 行 `from miles_portal.tenant.a2a.server import (`）新增一项，插在 `artifact_ids_from_job_result,` 之前：

```python
    app_error_envelope,
```

`handle_a2a_rpc` 改为（docstring 与新增行见下，**其余保持逐字不变**）：

```python
) -> dict:
    """JSON-RPC 2.0 分发入口：分发并统一留租户审计。

    审计放在这一层而非各 ``_handle_*`` 内：一次调用只该有一条流水，且 ``outcome`` 由最终
    信封决定（有 ``error`` 即失败），不必在各处重复判定。

    ``AppError`` 在这一层收口：各 ``_handle_*`` 的逐点映射是第一道（语义更精确），但只要
    某个 handler 漏捕、或捕得比业务异常更宽，异常就会落到 ``except AppError`` 被译成
    JSON-RPC 信封 —— 对端拿到的形状与逐点映射一致，且尾部那条统一审计能把原始类型与
    状态码记进 ``detail.errorType`` / ``detail.errorStatus``。
    """
    started = time.monotonic()
    method = payload.get("method") if isinstance(payload, dict) else None
    req_id = payload.get("id") if isinstance(payload, dict) else None
    action = _AUDIT_ACTION_BY_METHOD.get(method) if isinstance(method, str) else None
    # ``action`` 非空只可能来自「``method`` 是表内键」，此处重判一次让 ``method`` 收窄为
    # ``str``，不给调用点留下「靠运气成立」的类型不一致。
    if action is None or not isinstance(method, str):
        # 不支持的方法没有对应动作名，不编造流水。
        return await _dispatch_a2a_rpc(db, ctx, agent_id, payload, base_url=base_url)
    #: 被兜底接住的业务异常。非空时把原始类型与 status 记进审计（对外码已被压平）。
    origin: AppError | None = None
    try:
        envelope = await _dispatch_a2a_rpc(db, ctx, agent_id, payload, base_url=base_url)
    except AppError as exc:
        # 只有 handler 漏捕或捕得更宽才会走到这里 —— 是「映射归属」漏了，值得可查。
        origin = exc
        logger.warning(
            "A2A 业务异常经兜底译码: method=%s agent_id=%s errorType=%s status=%s",
            method,
            agent_id,
            type(exc).__name__,
            exc.status_code,
        )
        envelope = app_error_envelope(method, req_id, exc)
    except Exception:
        # 未捕获异常逸出（DB / 存储故障）：先留痕再**原样重抛**。这里是失败路径上唯一的
        # 留痕机会 —— 吞掉异常会把 500 变成 200，把故障伪装成成功。
        # detail 走 ``_rpc_audit_detail``：``contextId`` 与正常路径同一长度闸口，避免兑底
        # 路径把超长值写进租户可见面、或漏掉本可取到的会话标识。
        await write_a2a_audit(
            ctx=ctx,
            agent_id=agent_id,
            action=action,
            outcome=AUDIT_OUTCOME_FAILED,
            detail=_rpc_audit_detail(
                payload,
                {"error": {"code": INTERNAL_ERROR}},
                started=started,
                method=method,
            ),
        )
        raise
    await write_a2a_audit(
        ctx=ctx,
        agent_id=agent_id,
        action=action,
        outcome=_rpc_audit_outcome(envelope),
        detail=_rpc_audit_detail(payload, envelope, started=started, method=method, origin=origin),
    )
    return envelope
```

`_rpc_audit_detail` 签名与末尾补 `origin`：

```python
def _rpc_audit_detail(
    payload: object,
    envelope: object,
    *,
    started: float,
    method: str,
    origin: AppError | None = None,
) -> dict:
    """审计细节：方法、耗时，以及能低成本取到的任务/会话标识与错误码。

    ``origin`` 非空表示该次调用由兜底译码：额外记原始异常类型与 HTTP status。对外码已被
    域规则压平（权限读不出真实原因），这两项是租户可见面上唯一的补偿。**只记类型与状态码**
    —— ``AppError`` 文案可能夹内部实现细节，`aud_logs` 是租户可见面。
    """
```

并在 `return detail` 之前追加：

```python
    if origin is not None:
        detail["errorType"] = type(origin).__name__
        detail["errorStatus"] = origin.status_code
    return detail
```

- [ ] **Step 4: 跑用例确认通过（GREEN）**

```bash
cd backend && uv run python -m pytest tests/tenant/a2a tests/api -q
```

预期：全绿。特别注意这两条既有断言**不得**变红（它们钉住 `origin=None` 时 `detail` 键集不变）：
`tests/api/test_a2a_server_api.py::test_tasks_get_foreign_tenant_returns_jsonrpc_not_platform_envelope` 的
`set(recorded[0]["detail"]) == {"method", "taskId", "errorCode", "durationMs"}`。

- [ ] **Step 5: 证伪（必须做，记录输出）**

把 `except AppError as exc:` 这一分支整体注释掉（连 `origin = exc` 一起），重跑 Step 2 的命令。

预期两件事：`test_tasks_cancel_race_maps_not_found_at_rpc_layer` 与 `test_rpc_layer_maps_uncaptured_app_error` 变 RED（分别因 `-32603` 与异常重抛）。然后**恢复**该分支并确认 Step 4 再次全绿。

- [ ] **Step 6: 提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI && git add -A && git commit -F - <<'EOF'
fix(a2a): RPC 层兜底 AppError，修掉 tasks/cancel 竞态的 500 逃逸

_handle_tasks_cancel 第二个 try 只捕 BadRequestError，任务在归属校验之后、取消之前
被删时 NotFoundError 逸出成 HTTP 500 平台信封（审计还把它误记成 -32603）。改为在
handle_a2a_rpc 收口：逐点映射仍是第一道，漏网的在这里译成 JSON-RPC 信封，并借尾部
统一审计把原始 errorType / errorStatus 记进租户可见面。

未预期异常口径不变：仍审计 -32603 后原样重抛，保留 500 的监控语义。
EOF
```

---

### Task 3: `message/send` 停止截获业务异常（修 E3）

**Files:**
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/server.py`（`_handle_message_send` 第 236-241 行）
- Test: `backend/tests/tenant/a2a/test_a2a_server_card.py`（在 `# --- 4. Task 生命周期`（第 733 行）**之前**插入新小节，即落在线第 3 段末尾）

**Interfaces:**
- Consumes: Task 2 的兜底（E3 的码与审计都在那里产生）。
- Produces: `_handle_message_send` 不再消费 `AppError`；`message/send` 的合规拦截与配额拒绝对外从 `-32603` 变为 `-32602`。

**前置事实（写用例时用真实来源，不要编）**：合规拦截的真实异常是 `BadRequestError(f"输入内容包含敏感词，已拦截：{first.word}")`（`miles-portal/.../tenant/compliance/services/compliance/intercept.py:67`）。

- [ ] **Step 1: 写 2 条失败用例**

在 `backend/tests/tenant/a2a/test_a2a_server_card.py` 的 `# --- 4. Task 生命周期` 之前（即第 733 行之前）插入整段：

```python
# --- 3.1 message/send 的业务异常不再被 handler 吞成内部错误（治 E3） ----------- #


@pytest.mark.asyncio
async def test_message_send_maps_compliance_block_to_invalid_params(monkeypatch, a2a_audit_recorder):  # noqa: ANN001
    """合规拦截曾被误标成 `-32603`「服务端内部错误」，对端据此会去重试。

    真实来源：`compliance/intercept.py` 对命中敏感词的入站消息抛
    `BadRequestError("输入内容包含敏感词，已拦截：…")`。
    """

    async def fake_chat(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise BadRequestError("输入内容包含敏感词，已拦截：某词")

    monkeypatch.setattr(server_svc, "run_published_agent_chat", fake_chat)
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "message/send",
        "params": {"message": {"parts": [{"kind": "text", "text": "你好"}]}},
    }

    envelope = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, payload, base_url=BASE)

    assert envelope["error"]["code"] == server_mod.INVALID_PARAMS
    assert "拦截" in envelope["error"]["message"]
    assert len(a2a_audit_recorder) == 1
    assert a2a_audit_recorder[0]["detail"]["errorCode"] == server_mod.INVALID_PARAMS
    assert a2a_audit_recorder[0]["detail"]["errorType"] == "BadRequestError"
    assert a2a_audit_recorder[0]["detail"]["errorStatus"] == 400


@pytest.mark.asyncio
async def test_message_send_maps_quota_forbidden_to_invalid_params(monkeypatch, a2a_audit_recorder):  # noqa: ANN001
    """配额/权限类 `ForbiddenError` 同理：不再是「内部错误」，但对外也读不出真实原因（已知取舍）。"""

    async def fake_chat(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise ForbiddenError("本月配额已用尽")

    monkeypatch.setattr(server_svc, "run_published_agent_chat", fake_chat)
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "message/send",
        "params": {"message": {"parts": [{"kind": "text", "text": "你好"}]}},
    }

    envelope = await server_svc.handle_a2a_rpc(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, payload, base_url=BASE)

    assert envelope["error"]["code"] == server_mod.INVALID_PARAMS
    assert a2a_audit_recorder[0]["detail"]["errorType"] == "ForbiddenError"
    assert a2a_audit_recorder[0]["detail"]["errorStatus"] == 403
```

- [ ] **Step 2: 跑用例确认失败（RED）**

```bash
cd backend && uv run python -m pytest tests/tenant/a2a/test_a2a_server_card.py -q -k "message_send_maps"
```

预期：两条都因 `assert -32603 == -32602` 失败，且 `detail` 里没有 `errorType`。**这两条即使 Task 2 已完成也必须红** —— 若它们是绿的，说明 Task 2 的兜底被 handler 挡住了（正是本任务要修的那件事），先别改代码，回报。

- [ ] **Step 3: 停止截获**

`backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/server.py` 的 `_handle_message_send` 第二段改为：

```python
    try:
        response = await run_published_agent_chat(db, ctx, agent_id, text, conversation_id=context_id)
    except AppError:
        # 业务异常（合规拦截的 BadRequestError、配额的 ForbiddenError …）不在此处译码：交给
        # ``handle_a2a_rpc`` 的统一兜底 —— 既拿到一致的域映射（都在 ``message/send`` 域，故为
        # -32602），也让审计能记下原始 ``errorType``/``errorStatus``。若在这里吞成 -32603，
        # 「配额用尽」「命中敏感词」都会被报成「服务端内部错误」，对端会去重试。
        raise
    except Exception as exc:
        # 对端只拿到 JSON-RPC 错误信封；本平台侧必须留栈，否则线上无法定位。
        logger.exception("A2A message/send 执行失败: agent_id=%s", agent_id)
        return jsonrpc_error(req_id, INTERNAL_ERROR, f"智能体执行失败: {exc}")
```

**不要**在这里自己拼信封：异常一旦在 handler 内被消费，外层就拿不到原始异常对象，审计也就写不出 `errorType`。

- [ ] **Step 4: 跑用例确认通过（GREEN）**

```bash
cd backend && uv run python -m pytest tests/tenant/a2a tests/api -q
```

预期：全绿。**必须确认既有用例里没有依赖 `-32603` 的**：

```bash
cd backend && rg -n "32603" tests/tenant/a2a/test_a2a_server_card.py tests/api/test_a2a_server_api.py
```

若有 `message/send` 相关的 `-32603` 断言，说明它钉的是本批要改的行为，需要人工判断——**报告，不要自行改断言**。

- [ ] **Step 5: 证伪（必须做，记录输出）**

删掉刚加的 `except AppError: raise` 两行，重跑 Step 2 命令。预期两条变 RED（回到 `-32603` 且无 `errorType`）。恢复后确认 Step 4 再次全绿。

- [ ] **Step 6: 提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI && git add -A && git commit -F - <<'EOF'
fix(a2a): message/send 不再把业务异常吞成 -32603

合规拦截抛 BadRequestError、配额命中抛 ForbiddenError，二者原先被 message/send 的宽
except 一并译成「服务端内部错误」，对端据此会去重试。改为让业务异常穿过 handler，
交给 RPC 层统一兜底：对外是 -32602，审计里保留原始 errorType / errorStatus。
EOF
```

---

### Task 4: 产物下载补齐三档失败留痕并将跨租户压成 404（修 E1）

**Files:**
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/server.py`（`read_task_artifact` 第 296-334 行；新增私有 helper 紧随其后）
- Test: `backend/tests/tenant/a2a/test_a2a_server_card.py`（`# --- 5. 产物下载归属校验` 段内，`test_task_artifact_failure_is_audited`（第 1675 行）之后）

**Interfaces:**
- Consumes: 既有 `load_owned_agent_task`、`artifact_ids_from_job_result`、`AttachmentService.read_attachment_bytes`、`write_a2a_audit`、`streaming.elapsed_ms`。
- Produces: `read_task_artifact` 的异常契约变为「跨租户附件抛 `NotFoundError('附件不存在')`，其余 `AppError` 原样重抛，非 `AppError` 原样重抛；**每条失败路径恰好一条 `failed` 流水**」。视图层（Task 5）依赖该契约给出 404/400/500。

- [ ] **Step 1: 写 3 条失败用例**

在 `backend/tests/tenant/a2a/test_a2a_server_card.py` 的 `# --- 6. message/stream` 之前（即第 1146 行之前）插入整段：

```python
# --- 5.1 产物下载的失败留痕与跨租户不确认存在性（治 E1） ---------------------- #


def _artifact_getter(job):  # noqa: ANN001, ANN202
    """把 ``get_generative_job_for_tenant`` 换成返回指定 job 的替身。"""

    async def _get(_db, _ctx, _job_id):  # noqa: ANN001
        return job

    return _get


def _failing_attachments(exc: Exception):  # noqa: ANN202
    """把 ``AttachmentService`` 换成「读字节即抛」的替身。"""

    class _FakeAttachments:
        def __init__(self, _db, _ctx) -> None:
            pass

        async def read_attachment_bytes(self, _attachment_id):  # noqa: ANN001
            raise exc

    return _FakeAttachments


@pytest.mark.asyncio
async def test_read_task_artifact_audits_not_ready_attachment_exactly_once(monkeypatch, a2a_audit_recorder):  # noqa: ANN001
    """附件未就绪（400）此前**零流水**，与 docstring 的「成败都留一条」相矛盾。

    判别力点：本用例断言 `len(...) == 1`。若在 `except` 块里 `raise` 新异常时被同一
    `try` 的后续 `except` 二次捕获，就会变成两条 —— 这是本段唯一容易写错的地方。
    """
    attachment_id = uuid4()
    job = _artifact_job(agent_id=AGENT_ID, attachments=(str(attachment_id),))
    monkeypatch.setattr(server_svc, "get_generative_job_for_tenant", _artifact_getter(job))
    monkeypatch.setattr(server_svc, "AttachmentService", _failing_attachments(BadRequestError("附件文件未就绪")))

    with pytest.raises(BadRequestError):
        await server_svc.read_task_artifact(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, job.id, attachment_id)

    assert len(a2a_audit_recorder) == 1
    assert [r["action"] for r in a2a_audit_recorder] == [server_mod.AUDIT_ACTION_ARTIFACT_DOWNLOAD]
    assert a2a_audit_recorder[0]["outcome"] == server_mod.AUDIT_OUTCOME_FAILED
    assert a2a_audit_recorder[0]["detail"]["errorCode"] == server_mod.INVALID_PARAMS
    assert a2a_audit_recorder[0]["detail"]["errorType"] == "BadRequestError"
    assert a2a_audit_recorder[0]["detail"]["errorStatus"] == 400
    assert a2a_audit_recorder[0]["detail"]["taskId"] == str(job.id)


@pytest.mark.asyncio
async def test_read_task_artifact_normalizes_foreign_attachment_to_not_found(monkeypatch, a2a_audit_recorder):  # noqa: ANN001
    """跨租户附件对外 404 而非 403：403 会向对端确认「该附件存在于别的租户」。

    `AttachmentService` 不改语义（跨租户仍抛 `ForbiddenError`，它对内部调用方是对的）——
    「不确认存在性」是 A2A 对外面自己的职责。
    """
    attachment_id = uuid4()
    job = _artifact_job(agent_id=AGENT_ID, attachments=(str(attachment_id),))
    monkeypatch.setattr(server_svc, "get_generative_job_for_tenant", _artifact_getter(job))
    monkeypatch.setattr(server_svc, "AttachmentService", _failing_attachments(ForbiddenError("无权访问该租户资源")))

    with pytest.raises(NotFoundError) as exc:
        await server_svc.read_task_artifact(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, job.id, attachment_id)

    assert str(exc.value) == "附件不存在"
    # ``from None``：不把「无权访问该租户资源」这类内部措辞串进上下文
    assert exc.value.__cause__ is None and exc.value.__suppress_context__ is True
    assert len(a2a_audit_recorder) == 1
    assert a2a_audit_recorder[0]["outcome"] == server_mod.AUDIT_OUTCOME_FAILED
    assert a2a_audit_recorder[0]["detail"]["errorCode"] == server_mod.TASK_NOT_FOUND
    # 对外被压成 404 后，租户可见面上仍能读出真实原因是越租户
    assert a2a_audit_recorder[0]["detail"]["errorType"] == "ForbiddenError"
    assert a2a_audit_recorder[0]["detail"]["errorStatus"] == 403


@pytest.mark.asyncio
async def test_read_task_artifact_audits_storage_failure_and_reraises(monkeypatch, a2a_audit_recorder):  # noqa: ANN001
    """存储/DB 故障此前零流水；原样重抛不变（仍由全局处理器给 500）。"""
    attachment_id = uuid4()
    job = _artifact_job(agent_id=AGENT_ID, attachments=(str(attachment_id),))
    monkeypatch.setattr(server_svc, "get_generative_job_for_tenant", _artifact_getter(job))
    monkeypatch.setattr(server_svc, "AttachmentService", _failing_attachments(RuntimeError("oss 不可用")))

    with pytest.raises(RuntimeError):
        await server_svc.read_task_artifact(_Db(agent=_agent()), SimpleNamespace(), AGENT_ID, job.id, attachment_id)

    assert len(a2a_audit_recorder) == 1
    assert a2a_audit_recorder[0]["detail"]["errorCode"] == server_mod.INTERNAL_ERROR
    assert "errorType" not in a2a_audit_recorder[0]["detail"]
```

- [ ] **Step 2: 跑用例确认失败（RED）**

```bash
cd backend && uv run python -m pytest tests/tenant/a2a/test_a2a_server_card.py -q -k read_task_artifact
```

预期：3 条新用例红（未就绪/存储故障零流水、跨租户抛的是 `ForbiddenError` 而非 `NotFoundError`）；已有的 `test_read_task_artifact_returns_bytes_for_own_task` / `..._hides_task_of_other_agent` / `test_task_artifact_failure_is_audited` 仍绿。

- [ ] **Step 3: 实现三档留痕与归一**

`backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/server.py` 的 `read_task_artifact` 改为：

```python
    started = time.monotonic()
    try:
        job = await load_owned_agent_task(db, ctx, agent_id, task_id)
        if str(attachment_id) not in artifact_ids_from_job_result(job.result):
            raise NotFoundError("附件不是该任务的产物")
        data, mime, filename = await AttachmentService(db, ctx).read_attachment_bytes(attachment_id)
    except NotFoundError:
        # 含 load_owned_agent_task 的各种「不存在」与「非本任务产物」
        await _audit_artifact_failure(ctx, agent_id, task_id, started, TASK_NOT_FOUND)
        raise
    except ForbiddenError as exc:
        # 跨租户附件：与「非本任务产物」同口径回 404，不向对端确认存在性。归一放在 A2A
        # 对外面而非 AttachmentService —— 后者对内部调用方（工作台附件列表等）是对的。
        await _audit_artifact_failure(ctx, agent_id, task_id, started, TASK_NOT_FOUND, origin=exc)
        raise NotFoundError("附件不存在") from None
    except AppError as exc:
        # 如「附件文件未就绪」（400）。状态码由全局处理器给，此处只补留痕。
        await _audit_artifact_failure(ctx, agent_id, task_id, started, INVALID_PARAMS, origin=exc)
        raise
    except Exception:
        # 存储 / DB 故障：留痕后原样重抛 → HTTP 500 平台信封（与 RPC 层口径一致）。
        await _audit_artifact_failure(ctx, agent_id, task_id, started, INTERNAL_ERROR)
        raise
    await write_a2a_audit(
        ctx=ctx,
        agent_id=agent_id,
        action=AUDIT_ACTION_ARTIFACT_DOWNLOAD,
        outcome=AUDIT_OUTCOME_OK,
        detail={"taskId": str(task_id), "durationMs": streaming.elapsed_ms(started)},
    )
    return data, mime, filename
```

并在 `read_task_artifact` **之后**新增（放在它与下一个函数之间）：

```python
async def _audit_artifact_failure(
    ctx: TenantContext,
    agent_id: UUID,
    task_id: UUID,
    started: float,
    error_code: int,
    *,
    origin: AppError | None = None,
) -> None:
    """产物下载失败留痕：越权尝试与存储故障都是排查线索，不能只在成功时记。

    ``origin`` 非空时额外记原始异常类型与 HTTP status —— 对外的 ``errorCode`` 已被压平
    （跨租户与「非本任务产物」都回 ``TASK_NOT_FOUND``），这是租户可见面上唯一能读出真实
    原因的出口。只记类型与状态码，不记 message。
    """
    detail: dict = {"taskId": str(task_id), "errorCode": error_code, "durationMs": streaming.elapsed_ms(started)}
    if origin is not None:
        detail["errorType"] = type(origin).__name__
        detail["errorStatus"] = origin.status_code
    await write_a2a_audit(
        ctx=ctx,
        agent_id=agent_id,
        action=AUDIT_ACTION_ARTIFACT_DOWNLOAD,
        outcome=AUDIT_OUTCOME_FAILED,
        detail=detail,
    )
```

同步把 `read_task_artifact` 的 docstring 结尾那句「成败都留一条审计流水（「谁把产物取走了」要查得到）。」补成：

```
    授权精确到「该智能体 · 该任务 · 该产物」：先验任务归属，再验附件确为该任务产物，
    否则本租户任意附件都能被取走。成败都留一条审计流水（「谁把产物取走了」要查得到）；
    跨租户附件对外归一为「附件不存在」（404），不确认存在性。
```

- [ ] **Step 4: 跑用例确认通过（GREEN）**

```bash
cd backend && uv run python -m pytest tests/tenant/a2a tests/api -q
```

预期：全绿。

- [ ] **Step 5: 证伪（必须做，记录输出）**

把 `except ForbiddenError as exc:` 分支整体注释掉，重跑 Step 2。预期 `test_read_task_artifact_normalizes_foreign_attachment_to_not_found` 变 RED（抛 `ForbiddenError` 而非 `NotFoundError`）。恢复后再把 `except AppError as exc:` 分支注释掉，重跑，预期 `..._audits_not_ready_attachment_exactly_once` 变 RED（零流水）。两次都恢复并确认 Step 4 全绿。

- [ ] **Step 6: 提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI && git add -A && git commit -F - <<'EOF'
fix(a2a): 产物下载补齐失败留痕，跨租户附件对外归一为 404

read_task_artifact 只捕 NotFoundError，附件未就绪（400）、跨租户附件（403）与存储
故障（任意异常）三类全部逸出成平台信封且零审计，与它自己 docstring 的「成败都留一条
流水」相矛盾；跨租户那条更会向对端确认「该附件存在于别的租户」。

改为三档分别留痕并归位：跨租户压成 NotFoundError("附件不存在")，其余 AppError 与
非 AppError 原样重抛（仍由全局处理器给 400/500）。审计多记 errorType / errorStatus，
补偿对外码被压平后丢失的原因。
EOF
```

---

### Task 5: 视图层纵深防御与 HTTP 面验收

**Files:**
- Modify: `backend/packages/miles-openapi/src/miles_openapi/views/a2a_server.py`（import 第 20 行与第 28-33 行；`a2a_jsonrpc` 第 108-114 行）
- Test: `backend/tests/api/test_a2a_server_api.py`（文件末尾，`test_artifact_endpoint_rate_limited_uses_platform_envelope` 之后）

**Interfaces:**
- Consumes: Task 2/3/4 的服务层行为；视图层已有的 `_stream_or_json`、`req_id`、`client_ip`。
- Produces: `a2a_jsonrpc` 对三个分发点的 `AppError` 兜底（纵深防御）。HTTP 形状：JSON-RPC 路径 `AppError` → HTTP 200 + JSON-RPC 信封；产物下载 404/400/500 平台信封 + 审计。

- [ ] **Step 1: 写 4 组失败用例（5 个测试项）**

先补 import：`backend/tests/api/test_a2a_server_api.py` 第 16 行改为

```python
from miles_common.exceptions import BadRequestError, ForbiddenError, NotFoundError
```

在文件末尾（`test_artifact_endpoint_rate_limited_uses_platform_envelope` 之后）追加：

```python
# --- 错误封口：业务异常不得逸出成平台信封 ------------------------------------- #


def _published_agent():  # noqa: ANN202
    """已发布 custom 智能体：`message/send` 的前置门槛要求它。"""
    agent = Agent()
    agent.id = AGENT_ID
    agent.agent_type = AgentType.CUSTOM
    agent.status = AgentStatus.ENABLED
    agent.config = {A2A_PUBLISH_FLAG: True}
    agent.deleted_at = None
    return agent


class _AgentDb:
    """本组用例只用到 ``get``（取智能体）。注意 `load_published_agent` 里是 `await db.get(...)`。"""

    async def get(self, _model, _id):  # noqa: ANN001
        return _published_agent()

    async def commit(self):  # noqa: ANN201
        pass


def _use_agent_db(app):  # noqa: ANN001, ANN202
    """把 `get_db` 覆盖成 `_AgentDb`（`as_a2a` 默认给的是 `object()`）。"""

    async def override_db():  # noqa: ANN202
        yield _AgentDb()

    app.dependency_overrides[get_db] = override_db


@pytest.mark.asyncio
async def test_tasks_cancel_race_returns_jsonrpc_not_platform_envelope(as_a2a, api_client, monkeypatch):
    """E2 的 HTTP 面：`cancel_job` 竞态 `NotFoundError` → HTTP 200 + `-32001`，不是 500。

    `tasks/cancel` 不查智能体发布状态，故本用例只需替换「取任务 / 取消 / 审计」三个 I/O 出口。
    """
    job = SimpleNamespace(
        id=uuid4(),
        status=SimpleNamespace(value="running"),
        params={},
        result=None,
        source_ref_type="agent",
        source_ref_id=AGENT_ID,
    )

    async def _owned(_db, _ctx, _job_id):  # noqa: ANN001
        return job

    class _Raced:
        def __init__(self, _db, _ctx) -> None:
            pass

        async def cancel_job(self, _job_id):  # noqa: ANN001
            raise NotFoundError("生成任务不存在")

    recorded: list[dict] = []

    async def _write(**kwargs):  # noqa: ANN003
        recorded.append(kwargs)

    monkeypatch.setattr(a2a_svc, "get_generative_job_for_tenant", _owned)
    monkeypatch.setattr(a2a_svc, "GenerativeJobService", _Raced)
    monkeypatch.setattr(a2a_svc, "write_a2a_audit", _write)

    resp = await api_client.post(
        RPC_PATH,
        json={"jsonrpc": "2.0", "id": 4, "method": "tasks/cancel", "params": {"id": str(job.id)}},
    )

    assert resp.status_code == 200
    body = resp.json()
    # 键集等值即「没有逸出到全局处理器」：平台信封是 {code,message,data,trace_id}
    assert set(body) == {"jsonrpc", "id", "error"}
    assert body["id"] == 4
    assert body["error"]["code"] == -32001
    assert len(recorded) == 1
    assert recorded[0]["detail"]["errorType"] == "NotFoundError"
    assert recorded[0]["detail"]["errorStatus"] == 404


@pytest.mark.asyncio
async def test_message_send_compliance_block_returns_invalid_params(as_a2a, api_client, monkeypatch):
    """E3 的 HTTP 面：合规拦截（`BadRequestError`）→ HTTP 200 + `-32602`，不是 `-32603`。"""

    async def _blocked(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise BadRequestError("输入内容包含敏感词，已拦截：某词")

    recorded: list[dict] = []

    async def _write(**kwargs):  # noqa: ANN003
        recorded.append(kwargs)

    _use_agent_db(as_a2a)
    monkeypatch.setattr(a2a_svc, "run_published_agent_chat", _blocked)
    monkeypatch.setattr(a2a_svc, "write_a2a_audit", _write)

    resp = await api_client.post(
        RPC_PATH,
        json={
            "jsonrpc": "2.0",
            "id": 6,
            "method": "message/send",
            "params": {"message": {"parts": [{"kind": "text", "text": "你好"}]}},
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"jsonrpc", "id", "error"}
    assert body["error"]["code"] == -32602
    assert len(recorded) == 1
    assert recorded[0]["detail"]["errorType"] == "BadRequestError"
    assert recorded[0]["detail"]["errorStatus"] == 400


@pytest.mark.parametrize(
    ("exc", "expected_status", "expected_code", "expected_type"),
    [
        # 跨租户附件：修复前是 **403**（等于向对端确认「该附件存在于别的租户」），且零流水
        (ForbiddenError("无权访问该租户资源"), 404, -32001, "ForbiddenError"),
        # 附件未就绪：修复前是 400 但**零流水**（与 docstring 的「成败都留一条」相矛盾）
        (BadRequestError("附件文件未就绪"), 400, -32602, "BadRequestError"),
    ],
)
@pytest.mark.asyncio
async def test_artifact_endpoint_failure_maps_status_and_audits(  # noqa: ANN001
    as_a2a, api_client, monkeypatch, exc, expected_status, expected_code, expected_type
):
    """E1 的 HTTP 面：该端点是普通 HTTP 下载，形状本来就是平台信封 —— 要验的是**状态码**与**留痕**。

    非 ``AppError``（存储故障）→ 500 的情形不在本用例：``ASGITransport`` 默认
    ``raise_app_exceptions=True``，应用层重抛的异常会在测试客户端里直接抛出，拿不到响应。
    该情形由服务层用例（`test_read_task_artifact_audits_storage_failure_and_reraises`）锁定。
    """
    attachment_id, task_id = uuid4(), uuid4()
    job = SimpleNamespace(
        id=task_id,
        status=SimpleNamespace(value="success"),
        params={},
        result={"kind": "image", "attachment_ids": [str(attachment_id)], "mime_type": "image/png"},
        source_ref_type="agent",
        source_ref_id=AGENT_ID,
    )

    async def _owned(_db, _ctx, _job_id):  # noqa: ANN001
        return job

    class _FailingAttachments:
        def __init__(self, _db, _ctx) -> None:
            pass

        async def read_attachment_bytes(self, _attachment_id):  # noqa: ANN001
            raise exc

    recorded: list[dict] = []

    async def _write(**kwargs):  # noqa: ANN003
        recorded.append(kwargs)

    # 本路由只用这三个 I/O 出口（取任务 / 读字节 / 审计），其余全真，让请求经 ASGI 走完一次分发
    monkeypatch.setattr(a2a_svc, "get_generative_job_for_tenant", _owned)
    monkeypatch.setattr(a2a_svc, "AttachmentService", _FailingAttachments)
    monkeypatch.setattr(a2a_svc, "write_a2a_audit", _write)

    resp = await api_client.get(ARTIFACT_PATH.format(AGENT_ID, task_id, attachment_id))

    assert resp.status_code == expected_status
    body = resp.json()
    assert set(body) == {"code", "message", "data", "trace_id"}
    assert body["code"] == expected_code
    assert len(recorded) == 1
    assert recorded[0]["action"] == "a2a.artifact.download"
    assert recorded[0]["outcome"] == "failed"
    assert recorded[0]["detail"]["errorCode"] == expected_code
    assert recorded[0]["detail"]["errorType"] == expected_type
```

- [ ] **Step 2: 写视图层兜底的注入式用例**

```python
@pytest.mark.asyncio
async def test_rpc_view_converts_escaped_app_error_to_envelope(as_a2a, api_client, monkeypatch):
    """视图层兜底（纵深防御）：分发点逸出的 `AppError` 仍回 JSON-RPC 信封。

    **注入式用例**：两个流式入口当前无可达的 `AppError` 逸出点，故这里用替身直接把异常
    从分发点抛出 —— 它锁的是「这段兜底不被重构悄悄删掉」，**不是**缺陷回归闸门。
    """

    async def _escape(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise ForbiddenError("配额已用尽")

    monkeypatch.setattr(view_mod, "handle_a2a_rpc", _escape)

    resp = await api_client.post(
        RPC_PATH,
        json={"jsonrpc": "2.0", "id": 11, "method": "message/send", "params": {}},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"jsonrpc", "id", "error"}
    assert body["error"]["code"] == -32602
```

- [ ] **Step 3: 跑用例确认失败（RED）**

```bash
cd backend && uv run python -m pytest tests/api/test_a2a_server_api.py -q -k "race_returns or compliance_block or artifact_endpoint_failure or escaped_app_error"
```

预期：只有 `test_rpc_view_converts_escaped_app_error_to_envelope` **必然**红（视图层尚无兜底，`ForbiddenError` 逸出到全局处理器 → 403 平台信封）。其余三条是 Task 2/3/4 已修好行为的**跨层复验**：若它们已绿，是那三个任务的功劳，**如实记录**，不要当成 RED 证据。若 `escaped_app_error` 那条没红，说明异常根本没从视图抛出去，先停下排查。

- [ ] **Step 4: 实现视图层兜底**

`backend/packages/miles-openapi/src/miles_openapi/views/a2a_server.py`：

第 20 行改为：

```python
from miles_common.exceptions import AppError, NotFoundError
```

纯函数 import 块改为：

```python
from miles_portal.tenant.a2a.server import (
    PARSE_ERROR,
    RATE_LIMITED,
    agent_card_well_known_path,
    app_error_envelope,
    jsonrpc_error,
)
```

`a2a_jsonrpc` 第 108-114 行改为：

```python
    base_url = str(request.base_url)
    method = payload.get("method") if isinstance(payload, dict) else None
    try:
        if method == "message/stream":
            return _stream_or_json(await open_a2a_stream(db, ctx, agent_id, payload))
        if method == "tasks/resubscribe":
            return _stream_or_json(await open_task_subscription(db, ctx, agent_id, payload, base_url=base_url))
        envelope = await handle_a2a_rpc(db, ctx, agent_id, payload, base_url=base_url)
    except AppError as exc:
        # 纵深防御：服务层已按 ``method`` 逐点映射并在 RPC 层兜底，两个流式入口也各自消化了
        # 可预期的业务异常，故当前没有可达的逸出点。这段只是让「未来新增流式方法时漏捕」
        # 自动受保护 —— 三个分发点都只在回 JSON 之前抛，故统一回 JSON 信封是安全的。
        return JSONResponse(app_error_envelope(method, req_id, exc))
    return JSONResponse(envelope)
```

**注意**：本步**不改** `a2a_jsonrpc` 的 docstring（改了会触发 openapi 快照漂移）。

- [ ] **Step 5: 跑用例确认通过（GREEN）**

```bash
cd backend && uv run python -m pytest tests/api/test_a2a_server_api.py -q && cd .. && make openapi-check
```

预期：全绿且 `openapi-check` **不漂移**。若漂移，检查是否误改了 docstring；若确实必须改，则用 `make openapi-update` 更新 `backend/openapi/openapi.snapshot.json` 并在提交说明里点出。

- [ ] **Step 6: 提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI && git add -A && git commit -F - <<'EOF'
fix(a2a): 视图层为三处分流加 AppError 兜底并补 HTTP 面用例

服务层已在 RPC 层收口，视图层这一道是纵深防御：两个流式入口当前无可达逸出点，用例
只能注入式锁定（docstring 已注明不代表存在已知缺陷），价值在新增流式方法时自动受保护。

HTTP 面补齐三条跨层验收：tasks/cancel 竞态回 -32001、合规拦截回 -32602、跨租户产物
下载回 404 且留痕。
EOF
```

---

### Task 6: `attachment.py` docstring、文档同步与全量质量门

**Files:**
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/attachments/services/attachment.py`（`_get_or_raise` 第 178-179 行）
- Modify: `docs/guides/a2a.md`（`## 对外暴露` 段末 = 第 148 行前后；任务归属段第 102 行；产物下载段第 104 行；`## 审计` 段第 178-200 行）
- Modify: `docs/features/a2a-interconnect.md`（第 127 行错误码段）
- Modify: `docs/superpowers/specs/2026-09-20-a2a-task-lookup-tenant-boundary-design.md`（§5 第 149-154 行）

**Interfaces:**
- Consumes: Task 1-5 的最终行为（映射表、`errorType`/`errorStatus`、产物下载三档留痕）。
- Produces: 对外文档与实现一致；无残留的「只如实记录、不改码」式过时表述。

- [ ] **Step 1: 修正 `attachment.py` 的 docstring**

`backend/packages/miles-portal/src/miles_portal/tenant/attachments/services/attachment.py` 第 178-179 行改为：

```python
    async def _get_or_raise(self, attachment_id: UUID) -> Attachment:
        """按 ID 取未删附件并校验租户归属；缺失或已删抛 ``NotFoundError``，跨租户抛 ``ForbiddenError``。

        A2A 对外面会把跨租户压成 404（见 ``a2a.services.server.read_task_artifact``）——
        「不向对端确认存在性」是那一层自己的职责，本服务不改这一语义。
        """
```

**口径说明**：本仓其余兄弟服务的 `_get_or_raise`（`skills` / `tools` / `prompts` / `models` / `media_assets` / `categories`）对此**沉默**（不写跨租户语义），故只求「不再说谎」，**不要**顺手去给它们统一措辞。

- [ ] **Step 2: 更新指南的「错误与信封」小节**

在 `docs/guides/a2a.md` 的 `## 对外暴露（本平台作 Server）` 段末、`## 限流` 之前（约第 149 行）新增：

```markdown
### 错误与信封

调用端点的协议级错误一律回 **HTTP 200 + JSON-RPC 信封**（`{"jsonrpc":"2.0","id":…,"error":{"code":…,"message":…}}`），
对端据此把错误对回自己的 `id`。**不要**按平台信封 `{code,message,data,trace_id}` 解析。

| `error.code` | 含义 | 触发 |
|---|---|---|
| `-32700` / `-32600` | 解析错误 / 非法请求 | 请求体不是合法 JSON |
| `-32601` | 方法未找到 | 未实现的方法（如 `tasks/pushNotificationConfig/*`） |
| `-32602` | 参数错误 | `message/*` 域的业务异常（含合规拦截、配额/权限拒绝）、非法 `params.id`、超长 `contextId` |
| `-32603` | 内部错误 | `tasks/*` 域的冲突类业务异常；未预期故障（见下） |
| `-32000` | 限流 | 超限；HTTP 429 + `Retry-After` |
| `-32001` | 任务不存在 | 不属于该智能体的任务（含**其他租户**的任务）、`tasks/*` 域的 401/403/404 |
| `-32002` | 任务不可取消 | 任务已结束 |

**权限与冲突会被压平**：除 `tasks/*` 之外，业务异常的状态码不进入 `error.code`
（401/403/404 与 400 一律 `-32602`，409 与 5xx 一律 `-32603`），对端读不出真实原因 ——
这是为了不给出探测资源存在性的 oracle。原因记在租户审计的 `errorType` / `errorStatus`。

**例外**：未预期故障（DB / 对象存储等非业务异常）回 **HTTP 500 平台信封**，不保证
JSON-RPC 形状。对端须能按 HTTP 状态码兜底处理这一类。
```

- [ ] **Step 3: 收窄留痕例外并补产物下载段**

1. 第 102 行任务归属段的末句：

   - 原文：`（请求体无法解析、被限流、附件尚未就绪这三类前置失败除外）`
   - 改为：`（请求体无法解析、被限流这两类前置失败除外）`

2. 第 104 行产物下载段末句补：

   ```markdown
   非该任务产物、**跨租户的附件**、附件尚未就绪、以及存储读取故障都回 404/400/500 并**各留一条流水**；
   跨租户与「非该任务产物」不可区分（同为 404）。
   ```

- [ ] **Step 4: 改审计段（含改写过时的那一段）**

1. 动作表下方那句「记录内容为「谁（`apiKeyId`）…」」之后补：

   ```markdown
   当某次调用的业务异常由 RPC 层兜底译码时，`detail` 会额外带 `errorType`（异常类名）与
   `errorStatus`（HTTP 状态码）—— 对外错误码被压平后，这是租户可见面上唯一能读出真实原因的
   出口。同样**只记类型与状态码，不记 message**。
   ```

2. 末尾那段「同一个合规拦截在两个方法上的 `outcome` 并不一致…」**整段重写**（原文称「差异来自 send 侧的错误码映射，本次只如实记录、不改码」，本批正好改了那个码）：

   ```markdown
   同一个合规拦截在两个方法上的 `outcome` 并不一致：`message/send` 侧记为 `failed`、
   `message/stream` 侧记为 `rejected`。差异来自两个方法各自的判据 —— send 按最终信封**有无
   `error`** 判定，stream 按**终态帧状态**判定 —— 与错误码无关。两侧错误码现已一致：合规拦截
   在 send 侧是 `-32602`（参数错误），不再是早前被宽 except 误标的 `-32603`（内部错误）。
   ```

- [ ] **Step 5: 更新功能规格与上一批设计的残余**

1. `docs/features/a2a-interconnect.md` 第 127 行：

   - 原文：`JSON-RPC 协议级错误（解析 / 方法 / 参数）回 HTTP 200 + error 信封，执行异常回 -32603。`
   - 改为：`JSON-RPC 协议级错误（解析 / 方法 / 参数）回 HTTP 200 + error 信封；业务异常按域映射（tasks/* 的 401/403/404 → -32001，其余与 400 → -32602，409/5xx → -32603），未预期故障仍回 HTTP 500 平台信封。`

2. `docs/superpowers/specs/2026-09-20-a2a-task-lookup-tenant-boundary-design.md` §5 残余 #1 的两条子项改为已关闭：

   ```markdown
   1. ~~不做 `handle_a2a_rpc` 的 `AppError` 通用兜底。~~ **已由
      `2026-09-21-a2a-error-sealing-design.md` 关闭**：RPC 层已加兜底，下列两条不再以平台
      信封返回。
      - ~~`_handle_tasks_cancel` 第二个 `try` 里 `cancel_job` 的**竞态** `NotFoundError`…~~
        **已关闭**：现回 HTTP 200 + `-32001`。
      - ~~`_handle_message_send` 的 `except Exception` 会把 `ForbiddenError`（如配额超限）
        误标为 `-32603`…~~ **已关闭**：现回 `-32602` 并在审计里记 `errorType`。
   ```

   残余 #5（I2，跨租户探测内部不可区分）**保持不变**，并在其后补一句「本批不改变其状态」。

- [ ] **Step 6: 跑五道质量门**

```bash
cd backend && uv run python -m pytest -q && uv run ruff check . && uv run ruff format --check . && cd .. && make layers-check && make openapi-check
```

预期：五道全绿。（`openapi-check` 若漂移，只可能是 `attachment.py` 的 docstring —— 它不在 OpenAPI 面上，**不应**漂移。）

- [ ] **Step 7: 核对验收清单**

逐条对照 `docs/superpowers/specs/2026-09-21-a2a-error-sealing-design.md` §6，把已满足项打勾（**在 spec 文件里**改）。任何一条无法勾选的，如实报告，不要改口径迁就实现。

- [ ] **Step 8: 提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI && git add -A && git commit -F - <<'EOF'
docs(a2a): 同步错误封口口径并修正 attachment 的 docstring 谎言

指南新增「错误与信封」映射表（含「权限被压平」「500 不保证 JSON-RPC 形状」两条例外），
留痕例外收窄为「请求体无法解析、被限流」两类，产物下载段补跨租户 404 与各类失败留痕，
并重写审计段那段「合规拦截 outcome 不一致」—— 它当时称只如实记录、不改码，本批改了那个码。

attachment._get_or_raise 的 docstring 声称跨租户抛 NotFoundError，实际抛 ForbiddenError，
是全仓唯一一处会撒谎的同类 docstring；改为说真话，不顺手改语义。

功能规格与上一批设计的残余 #1/#2 一并标注为已关闭。
EOF
```

---

## 完成后

不要自行合并 `main`。汇报内容：

1. 每个 Task 的提交 sha（应为 6 笔）；
2. 每条新用例的 **RED 证据**（哪条断言、什么值），特别是 Task 2/3/4/5 的证伪输出；
3. 五道质量门的实际结果（通过数）；
4. `openapi-check` 是否漂移；
5. 计划与实际不符之处（含本计划里任何**你判断需要偏离**的步骤）—— 计划有问题要**报告并回填计划**，不要默默绕过。
