# A2A 出站任务轮询与 Task 状态准确性（Client 响应分类 / `timestamp` / `status.message`）Design

**日期**：2026-09-21
**范围**：`backend/packages/miles-portal/src/miles_portal/tenant/a2a/`、文档
**前置**：`2026-09-21-a2a-error-sealing-design.md`（A2A 对外面错误封口，已合并 `bc37217c`）

---

## 1. 问题

本批修两件事，它们同属「A2A 对外面的正确性」，且 (B) 直接决定 (A) 的可用性。

### 1.1 出站 Client 会把非回答当成「回答」（两个形态）

**形态一：纯 `Task` → 原始 JSON。**

本平台自己的 Server 在**生成任务未就绪**时回的就是 `Task`（`services/server.py:250-262`）：

```python
return jsonrpc_result(
    req_id,
    build_a2a_task(
        task_id=str(job.get("id")),
        context_id=context_id,
        state=to_a2a_task_state(str(job.get("status"))),
        timestamp=now_iso(),
    ),
)
```

它的形状是 `{"kind": "task", "id": …, "status": {"state": …, "timestamp": …}}` —— **没有 `message`，也没有 `artifacts`**。

而 Client 抽文本的逻辑（`client.py:133-151` `_text_from_result_payload`）依次找：

1. `result` 上的 `text` / `answer` / `content` / `message` 字符串键（`_RESULT_TEXT_KEYS`）
2. `result["message"]` 下的 `text` / `content` / `parts`
3. `result["artifacts"][0]["parts"][0]["text"]`

纯 `Task` 三条全不命中 → 返回 `None` → `_extract_text_from_response` 落到兜底：

```python
return str(result)[:4000]
```

**一段原始 JSON 被当作外部智能体的「回答」**，经 `invoke.py:189-199` 写进 `steps[].output_preview`，并以 `【外部 A2A · {name}】\n{answer}` 合入主模型的汇总素材（`invoke.py:200`）。

可达性：**必然**。两个 MilesAI 实例互联、且对方产生了生成任务（生图 / 生视频）时，对方回的正是 `Task`。

**形态二：JSON-RPC `error` → 错误消息冒充回答。**

`_extract_text_from_response` 刻意让 `error` 优先于 `result`（`client.py:161-164`），并由特征化测试锁定。该测试文件自述「重构前先在此锁定每种形状的取值、键序优先级与兜底行为」，其中一节的标题就是「**error 优先于 result**」：

```python
assert _extract_text_from_response({"error": {"message": "boom"}, "result": "r"}) == "boom"
assert _extract_text_from_response({"error": {"code": 1}}) == str({"code": 1})
assert _extract_text_from_response({"error": "plain"}) == "plain"
```

于是 `invoke_a2a_peer` 的 `if text: return text` 会把对端的**错误消息**当成功回答返回：`invoke.py:189-199` 记为 `steps[].type = "a2a_peer"`（**成功类型**），并作为 `【外部 A2A · {name}】\nboom` 进入主模型素材。

可达性：**宽**。A2A 协议级错误的标准形态正是 HTTP 200 + JSON-RPC `error`（`-32601` 方法未找到、`-32602` 参数错误、`-32603` 内部错误、`-32000` 限流、`-32001` 任务不存在、`-32002` 不可取消）—— 对端任何一个参数错误或内部错误，都会被我方读成「它回答了这句话」。

**这一行为是有意设计**（有专门的测试锁定），本批**不动 `_extract_text_from_response`**（§3.1）。要修的是 `invoke_a2a_peer` 的协议分类：它不该把「本次调用成功还是失败」这个判断交给一个「尽可能榨出文本」的函数。

### 1.2 Task 的 `timestamp` 与进度在入站侧也失真

`build_a2a_task` 的 5 个调用点**全部**传 `timestamp=now_iso()`，即**本次请求的时刻**，而不是任务状态被记录的时刻：

| # | 调用点 | 对象 |
|---|---|---|
| 1 | `services/server.py:256`（`message/send` 产物未就绪） | `response.generative_jobs` 的 dict |
| 2 | `services/server.py:402`（`tasks/get`） | `GenerativeJob`（ORM） |
| 3 | `services/server.py:435`（`tasks/cancel`） | `GenerativeJobOut` |
| 4 | `services/server.py:785`（`message/stream` 首帧） | 无（合成 `taskId`） |
| 5 | `subscription.py:248`（`tasks/resubscribe` 首帧） | `GenerativeJob`（ORM） |

后果：对端每次查询`都看到「刚刚更新」。A2A 规范里 `TaskStatus.timestamp` 的语义是「状态被记录的时间」，用请求时刻等于给出一个永不失效的假信号 —— 对端据此做新鲜度判断、超时或去重都会误判。

同一批调用点还**不产出 `status.message`**（`build_a2a_task` 只写 `state` + `timestamp`），而 `tasks/resubscribe` 的帧走 `build_a2a_status_update`、**带**进度文案（`subscription.py:269-270` 已在传 `progress_text(...)`）。于是同一任务的两条读取路径形状不一致：

- 对端轮询 `tasks/get` → 拿到状态，读不到任何进度说明
- 对端订阅 `tasks/resubscribe` → 每帧都带进度说明

### 1.3 交点

(A) 修好后，Client 会轮询 `tasks/get`。如果 (B) 不做，轮询拿到的每个 `Task` 都没有进度文案、`timestamp` 还每 2 秒变一次 —— Client 既无法向用户交代「卡在哪一步」，也无法据 `timestamp` 判断是否真有进展。**两件事分开做，(A) 的体感仍是「转 60 秒然后说还在跑」。**

三块工作都落在 `invoke_a2a_peer` 的**同一段响应处理代码**上（§3.1 的分流链）：Task 分流、`error` 分层、以及 §3.5 的 `tasks/cancel` 能力（只补不调用）。同一处代码、同一类取向，合成一个 spec。

---

## 2. 已确认的决策

1. **Client 采用有限轮询**：收到 `Task` 后用 `tasks/get` 轮询至终态，间隔 **2s**、总上限 **60s**；超时则回诚实文案 + `taskId`，交由对端自行继续查询。
2. **终态产物只给引用**：渲染 `artifactId` / `name` / `mimeType` / `uri`，**不下载**、不在 Client 侧透传凭证、不做二进制处理。
3. **不新增配置项**：轮询间隔与上限为模块常量。60s 与现有 `httpx.AsyncClient(timeout=60.0)` 同量级。
4. **`message/send` 的 Task 时间戳保持 `now_iso()`**：其来源 dict 只有 `{id, kind, status}`（`miles_ai/integrations/langchain/tool_agent/loop.py:40-42`），拿不到真实时间；为一条语义信息在写路径上加一次 DB 读不划算。该响应本就是「提交快照」，权威状态由随后 `tasks/get` 给出，故语义上可解释为「本快照生成时刻」。
5. **`message/stream` 首帧保持 `now_iso()`**：它的 `taskId` 是合成的（流开始就得定，生成任务 id 只有跑完才知道），没有真实对象可依。
6. **实现采用 Client 侧内聚**：轮询作 `client.py` 的私有 helper，`invoke_a2a_peer` 保持「返回 `str`」契约不变 —— 消费方 `invoke.py` 零改动。
7. **出站 `tasks/cancel` 只补能力、不自动调用**：新增 `cancel_a2a_peer_task`，但本批**不在任何路径调用它**。超时 ≠ 放弃 —— 自动取消会销毁对端租户即将到手的产物，而对端任务的产物属于对端用户（§3.5、§5 第 2 条）。
8. **「对端返回 `error`」采用分层修法**：在 `invoke_a2a_peer` 里先判顶层 `error` 即抛 `BadRequestError`；`_extract_text_from_response` 的 `error` 分支与其特征化测试**一字不动**（§3.1）。

---

## 3. 设计

### 3.1 Client 侧：判据与分流（`client.py`）

**判据用结构，不用 `kind`。** 0.3 规范里 `Task.kind` 是必填，但老 peer（以及本模块 `_extract_text_from_response` 一直在兼容的松散形状）不保证带它。用 `status.state` 存在来判定：

```python
def _looks_like_task(data: object) -> bool:
    """JSON-RPC 响应是否是一个 ``Task``（用结构判定，不依赖 ``kind``）。"""
    if not isinstance(data, dict):
        return False
    result = data.get("result")
    return isinstance(result, dict) and _task_state(result) is not None


def _task_state(task: dict) -> str | None:
    status = task.get("status")
    if not isinstance(status, dict):
        return None
    state = status.get("state")
    return state if isinstance(state, str) else None
```

分流插在 `invoke_a2a_peer` 的 `data = resp.json()` 之后、`_extract_text_from_response(data)` 之前，**顺序固定为 error → task → text**：

```python
data = resp.json()
#: 三者互斥。判断「本次调用成功还是失败」是本层的职责，不交给榨文本函数（§1.1 形态二）。
err = _jsonrpc_error(data)
if err is not None:
    # 对端已按 JSON-RPC 应答，说明 endpoint 形态已匹配：不再探测下一个，直接抛。
    raise BadRequestError(f"调用外部 A2A Agent「{peer.name}」失败：对端返回错误 {err[0]} {err[1]}")
if _looks_like_task(data):
    return await _resolve_agent_task(client, tasks_get_endpoints[index], data["result"], headers)
text = _extract_text_from_response(data)
if text:
    return text
```

```python
def _jsonrpc_error(data: object) -> tuple[object, str] | None:
    """顶层 ``error`` → ``(code, message)``；无 ``error`` 返回 ``None``。"""
    if not isinstance(data, dict) or "error" not in data:
        return None
    err = data["error"]
    if isinstance(err, dict):
        return err.get("code"), str(err.get("message") or err)
    return None, str(err)
```

两个必须保持的取向：

- **先判 `error`**：JSON-RPC 里 `error` 与 `result` 互斥。把「失败与否」交给 `_extract_text_from_response`，会让协议级失败被读成回答（`steps[].type = "a2a_peer"`）并进入主模型素材。
- **收到 JSON-RPC `error` 不再探测下一个 endpoint**：结构正确的 `error` 恰恰证明 endpoint 形态已匹配（对端解析并应答了请求）。这与既有「HTTP ≥ 400 → `continue`」的取向**有意不同** —— HTTP 层失败可能只是路径不对，协议级应答则说明找对了地方。

`_extract_text_from_response` 与 `_text_from_result_payload` **保持不动**：它们服务于 `Message` 响应与旧版松散形状，是前置分流之后的一层。其 `error` 分支从此在 `invoke_a2a_peer` 路径上不可达，但仍是该 helper 面向其他调用方的兼容能力。

**分流必须落在 `for url in message_endpoints` 循环的 `try` 之外**（或等价地保证 `_resolve_agent_task` 不向外抛 `httpx.RequestError` / `ValueError`）。否则外层 `except httpx.RequestError` / `except ValueError` 会把整段（最多 60s）的轮询结果丢掉，判为 `last_err` 后**再对第二个 endpoint 重跑一遍轮询** —— 最坏情况变成 120s 且用户拿不到任何结论。本设计靠 `_resolve_agent_task` 自己捕获这两类异常来满足该约束（§3.2），实现时不得把分流挪进 `try`。

相对地，`raise BadRequestError` 本身**可以**位于 `try` 内 —— 现有 `except (httpx.RequestError, ValueError)` 不会捕获它。但若实现时改动了该 `except` 子句（例如放宽成 `except Exception`），上面这条约束与 `_resolve_agent_task` 的异常处理都要重新审视。

### 3.2 Client 侧：有限轮询 `_resolve_agent_task`

新增常量：

```python
TASK_POLL_INTERVAL_SECONDS = 2.0
TASK_POLL_TIMEOUT_SECONDS = 60.0
TERMINAL_TASK_STATES = frozenset({"completed", "failed", "canceled", "rejected"})
#: 中断态：规范里 ``input-required`` / ``auth-required`` 同样「不再自行推进」，
#: 对端在等我们补充输入或凭证 —— 继续轮询只会白等，停止并如实回报。
INTERRUPTED_TASK_STATES = frozenset({"input-required", "auth-required"})
STOP_POLLING_TASK_STATES = TERMINAL_TASK_STATES | INTERRUPTED_TASK_STATES
```

主流程（四步，顺序有语义）：

```python
async def _resolve_agent_task(
    client: httpx.AsyncClient,
    url: str,
    task: dict,
    headers: dict[str, str],
) -> str:
    task_id = task.get("id")
    if not isinstance(task_id, str) or not task_id:
        return _render_agent_task(task, note="对端未给出任务 ID，无法继续查询")
    if _task_state(task) in STOP_POLLING_TASK_STATES:
        # 对端可能同步就绪：已终态 / 已中断就绝不轮询，一次多余请求也不发。
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
            # 本函数**不得**向上抛这两类异常，否则外层的 endpoint 循环会丢掉本段结果
            # 并对下一个 endpoint 重跑一遍轮询（§3.1）。
            return _render_agent_task(latest, note="继续查询失败（网络异常）")
        if isinstance(data, dict) and "error" in data:
            err = data["error"] if isinstance(data["error"], dict) else {}
            return _render_agent_task(
                latest,
                note=f"对端不支持继续查询（{err.get('code')} {err.get('message')}）",
            )
        if not _looks_like_task(data):
            # 形状不认识不是失败信号：保留最后一次已知状态，继续等。
            continue
        latest = data["result"]
        if _task_state(latest) in STOP_POLLING_TASK_STATES:
            return _render_agent_task(latest)

    return _render_agent_task(latest, note=f"已等待 {int(TASK_POLL_TIMEOUT_SECONDS)} 秒")
```

要点：

- **总时长由 `time.monotonic()` 的 deadline 控制**，与 `httpx` 的 `timeout=60.0` 无关 —— 后者是**单请求**的连接/读/写超时。这一点必须在实现时保持正确，否则 60s 上限形同虚设。
- `_tasks_get_payload(task_id)`：

```python
{"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "tasks/get", "params": {"id": task_id}}
```

- **任何失败信号都终止轮询**：HTTP ≥ 400、网络异常、JSON-RPC `error`。不重试 —— 把 60s 全耗在重试上，对端与用户都拿不到比「最后一次已知状态」更多的信息。「响应形状不认识」**不是**失败信号，继续等。
- 轮询中 429 属于 HTTP ≥ 400，直接回退快照，不做退避重试。

### 3.3 Client 侧：渲染 `_render_agent_task`

```python
def _render_agent_task(task: dict, *, note: str | None = None) -> str:
```

渲染为多行文本（会进 `steps[].output_preview`，也可能被拼进主模型素材）。**不带 peer 名** —— 调用方 `invoke.py:200` 已在 `【外部 A2A · {name}】` 前缀里给过，此处重复无益。

| Task 状态 | 首行 |
|---|---|
| `completed` | `外部任务已完成` |
| `failed` | `外部任务失败` |
| `canceled` | `外部任务已取消` |
| `rejected` | `外部任务被拒绝` |
| `input-required` | `外部任务需要补充输入` |
| `auth-required` | `外部任务需要鉴权` |
| `working` / `submitted` | `外部任务仍在进行（状态：{state}）` |
| `unknown` 或缺失 | `外部任务状态未知（状态：{state}）` |

随后依次追加（存在的才追加）：

1. **进展文案** —— 复用现有 `_first_part_text(status["message"].get("parts"))`（它取 `parts` 首项的 `text`，对 `file` part 返回 `None`，安全）。形如 `进展：45% 渲染中`。
2. **产物** —— 有 `artifacts` 时：

   ```text
   产物（2 个）：
   - image-1（image/png）：http://peer/api/v1/open/a2a/agents/<aid>/tasks/<tid>/artifacts/<attid>
   ```

   `name` 取 `file.name`，缺失回退 `artifactId`；`mimeType` 缺失则不显示括号。无下载地址（`parts` 里没有 `file`）时写 `（无下载地址）`。
3. **任务 ID** —— `任务 ID：{task_id}`，让上层/用户在超时后能自行继续查询。
4. **note** —— 超时或失败原因的说明。

新增私有 helper `_artifact_lines(artifacts: object) -> list[str]` 负责产物的逐条渲染；不下载、不展开内容。

### 3.4 Client 侧：endpoint 的对称探测

现有 `message/send` 会依次尝试两个 endpoint（`client.py:197-200`，兼容「每方法一个 REST 路径」与「单一 JSON-RPC 集合端点」两种部署）：

```python
endpoints = [urljoin(rpc_base + "/", "message/send"), rpc_base]
```

轮询必须打到**同一个部署形态**的对应位置，故构造对称列表并按**索引**选择：

```python
message_endpoints = [urljoin(rpc_base + "/", "message/send"), rpc_base]
tasks_get_endpoints = [urljoin(rpc_base + "/", "tasks/get"), rpc_base]
...
for index, url in enumerate(message_endpoints):
    ...
    if _looks_like_task(data):
        return await _resolve_agent_task(client, tasks_get_endpoints[index], data["result"], headers, peer_name=peer.name)
```

**第一轮探测出可用 endpoint 后固定使用**（由索引传递实现），避免每 2s 打两次请求。轮询复用同一个 `httpx.AsyncClient`（连接池复用已在 `async with` 作用域内）。

### 3.5 Client 侧：出站 `tasks/cancel` 能力（只补，不自动调用）

```python
async def cancel_a2a_peer_task(peer: A2aPeer, task_id: str) -> None:
    """请对端取消一个异步任务。成功返回；被拒或不可达抛 ``BadRequestError``。"""
```

- **前置校验**与 `invoke_a2a_peer` 一致：peer `status == active` 且 `agent_card_json` 非空，否则 `BadRequestError`
- **endpoint 对称探测**：`[urljoin(rpc_base + "/", "tasks/cancel"), rpc_base]`
- **请求体**：`{"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "tasks/cancel", "params": {"id": task_id}}`，认证复用 `build_auth_headers(peer.auth_config)`
- **成功判据**：HTTP < 400 **且**响应顶层无 `error`。成功后返回 `None` —— 取消没有信息量需要回报，失败一律走模块既有的异常契约（与 `invoke_a2a_peer` 全失败即 `BadRequestError` 同口径）
- **失败处理**：
  - 收到 JSON-RPC `error`（尤其 `-32002` 任务不可取消、`-32001` 不存在）→ **立即停止探测**（对端已应答，形态已匹配），抛 `BadRequestError` 带码与消息
  - HTTP ≥ 400 或网络异常 → 记录后试下一个 endpoint；全败抛 `BadRequestError`
- **本批不在任何路径调用它**（决策 7）：超时路径不碰。这个函数是为「上游将来出现明确的放弃语义」预留的能力（§5 第 2 条）

**为什么不自动调用**：对端任务的产物落在**对端租户**，属于对端用户。而 `invoke_a2a_peer` 是同步阻塞的，调用方没有「我放弃这个任务」这个信号 —— 60s 超时只表达「我不想再等了」。此时取消，很可能把一个再过几秒就完成的任务连同产物一起销毁。

### 3.6 Server 侧：抽出 `build_a2a_task_status`

`status` 的形状（含 `message` / `metadata.percent` / `metadata.a2aJobTaskId`）目前只在 `build_a2a_status_update` 里维护。`build_a2a_task` 也要产出同样的形状，抽成单一维护点：

```python
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
```

行为与现状逐字对齐：`text is None` 时**直接返回** `{"state", "timestamp"}`（不附 `status.message`）；否则构造 `build_a2a_agent_message(text, context_id, message_task_id)`，把 `job_task_id` 写进 `metadata.a2aJobTaskId`、`percent is not None` 时写进 `metadata.percent`，`metadata` 非空才挂上去。

`build_a2a_status_update` 改为调用它并把结果作为 `status`（其 `final` / `kind` / `taskId` 包装不变）。`build_a2a_task` 也改用它：

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
    ...
```

`text` / `percent` 的参数名与 `build_a2a_status_update` 一致，调用点读起来是同一种东西。

**已知边界（保持现状）**：`percent` 写在 `status.message` 上，故 `text` 为空时 `percent` 会被丢弃。既有行为，本批不改。

### 3.7 Server 侧：`timestamp_iso` 与 5 个调用点

```python
def timestamp_iso(value: datetime | None) -> str:
    """``datetime`` → A2A ``TaskStatus.timestamp``；非 ``datetime`` 回退当前时刻。"""
    return value.isoformat() if isinstance(value, datetime) else now_iso()
```

| # | 调用点 | 改动 |
|---|---|---|
| 1 | `services/server.py:256` | **不变**（决策 4） |
| 2 | `services/server.py:402` | `timestamp=timestamp_iso(job.updated_at)`；`text=progress_text(progress_message=job.progress_message, percent=job.progress_percent)`；`percent=job.progress_percent` |
| 3 | `services/server.py:435` | 同上（`job` 是 `cancel_job` 返回的 `GenerativeJobOut`，同样带 `updated_at` / `progress_message` / `progress_percent`） |
| 4 | `services/server.py:785` | **不变**（决策 5） |
| 5 | `subscription.py:248` | `timestamp=timestamp_iso(first.updated_at)`；`text` / `percent` 取自 `first`（与紧随其后的 status-update 帧同源，`:269-270` 已是这么取的） |

第 5 处的附带收益：首帧带上进度后，紧随其后的第一批 status-update 帧会经 `_progress_fingerprint`（`:275`）比对而**不重复发送**同一进度 —— 现有去重语义因此更完整（此前首帧无进度，订阅时刻的进度对端看不到）。

三处对象都已确认携带所需字段：`load_owned_agent_task` 返回 ORM `GenerativeJob`（`services/server.py:277-282`，带 `TimestampMixin` 的 `updated_at`、`progress_message`、`progress_percent`）；`GenerativeJobOut` 字段齐全（`generative/schemas/job.py:12-31`）；`subscription` 的 `first` 来自 `watch_generative_job` 的 ORM 对象。

### 3.8 测试

**Client 单元**（`backend/tests/tenant/agents/test_a2a_client_auth.py`，或同目录新建文件）：

| 用例 | 断言 |
|---|---|
| Task 已是终态 | 只发 1 次请求（不轮询），回答含产物 `name`/`mimeType`/`uri` |
| Task 已是 `input-required` | 只发 1 次请求；回答含「需要补充输入」与 `status.message` 里的提问 |
| Task 非终态 → 轮询到 `completed` | mock 序列 `working → working → completed`；回答含产物引用 |
| 轮询中途变为 `input-required` | **停止轮询**（不等满 60s），回答含「需要补充输入」 |
| 轮询超时 | 冻结 `time.monotonic`；回答含「仍在进行」+ `taskId` |
| `tasks/get` 回 `-32601` | 停止轮询；回答含「不支持继续查询」+ 最后一次状态 |
| 轮询中网络异常 | 停止轮询；回答含「网络异常」，且**不**触发第二个 endpoint 重跑 |
| Task 无 `id` | 不发轮询；回答含「未给出任务 ID」 |
| 轮询请求形状 | method=`tasks/get`、`params.id` 正确、endpoint 与 `message/send` 的探测结果对称 |
| 对端返回 JSON-RPC `error` | 抛 `BadRequestError`，文案含 `code` 与 `message`；**不**再探测第二个 endpoint；经 `invoke.py` 记为 `a2a_error` 而**非** `a2a_peer` |
| `tasks/cancel` 成功 | 返回 `None`；请求 method=`tasks/cancel`、`params.id` 正确 |
| `tasks/cancel` 回 `-32002` | 抛 `BadRequestError` 带对端码与消息；**不**再探测第二个 endpoint |
| `tasks/cancel` HTTP 500 / 网络异常 | 依次尝试两个 endpoint，全败抛 `BadRequestError` |
| 回归：`_extract_text_from_response` | 其 error / result 特征化测试**全部通过且一字未改** |
| 回归：`Message` 响应 | 行为与改动前一致（不被 Task 分流误捕） |

**Server 纯逻辑**（`backend/tests/tenant/a2a/test_a2a_server_card.py`）：

- `build_a2a_task` 带 `text` 时，`status` 形状与 `build_a2a_status_update` 的 `status` **逐键等价**（锁住单一维护点）
- 不带 `text` 时**不出现** `status.message`
- `percent` 写进 `metadata.percent`
- `timestamp_iso`：带 tz 的 `datetime` 原样 ISO；`None` 回退 `now_iso()`（蒙住 `now_iso` 断言）

**Server 集成**（`backend/tests/api/test_a2a_server_api.py`）：

- `tasks/get` 的 `status.timestamp` 来自固定 `updated_at` 的 job（构造后断言不等于「此刻」）
- `tasks/get` 带 `progress_message` 时出现 `status.message`
- `tasks/resubscribe` 首帧出现进度（并验证紧随的重复进度帧被去重）

**反证要求**：Client 侧的 Task 分流必须可被反证 —— 临时移除 `if _looks_like_task(data):` 分支后，「已是终态」与「轮询到 completed」两条用例必须转 RED；`build_a2a_task` 的 `text` 透传必须可被反证 —— 移除 `build_a2a_task_status` 调用后，纯逻辑与集成用例必须转 RED。

### 3.9 文档

- `docs/guides/a2a.md`：出站（「平台内引用外部（custom）」）段补「Client 收到 `Task` 后会以 2s 间隔轮询 `tasks/get`，至多 60s；超时回状态快照 + `taskId`，不下载产物」，并补「对端返回 JSON-RPC `error` 视为调用失败（记 `a2a_error`），不再把错误消息当回答」；`tasks/get` 段补 `status.timestamp` 与 `status.message` 的语义（真实状态时间 + 进度）
- `docs/features/a2a-interconnect.md`：同步出站行为
- 本次清点中「出站无 `tasks/get` 轮询」与「`tasks/get` 的 `status.timestamp` 用请求时刻」「`tasks/get` 不返回 `status.message`」三条标记为已关闭；新增「对端错误冒充回答」一条标记为已关闭

---

## 4. 为什么选「有限轮询」而不是「只做诚实降级」

「只做诚实降级」（把 Task 渲染成「已提交、待轮询」的文案）能修掉 §1.1 的缺陷 —— 原始 JSON 不再冒充回答 —— 但它**不解决互联可用性**：`invoke_a2a_peer` 是阻塞在对话链路里的（`execute_a2a_calls` 在对话响应生成过程中同步等待），它只能返回一个字符串给主模型汇总。若对端回 `Task` 而 Client 从不查询，主模型拿到的永远是「对方提交了一个任务」——两个 MilesAI 实例互联时，等于**永远拿不到对方的生成产物**。

有限轮询把这个缺口收在可接受的代价内：常见的生图 / 生视频在几十秒内完成，能真正闭环；超过 60s 的仍由对端自行继续 `tasks/get`（`taskId` 已给）。

不选「完整轮询（无上限）」的原因：那会把单次对话响应拖成分钟级，且 `tasks/resubscribe` 的长流上限已是既有的设计级残余（1800s），出站侧再引入一个无界等待会让链路超时预算无从计算。

---

## 5. 明确不做 / 已知残余

1. **出站 `message/stream`**：Client 仍只有 `message/send` + `tasks/get`，无逐 token 流式。
2. **出站 `tasks/cancel` 不自动调用**：能力已补（`cancel_a2a_peer_task`，§3.5），但本批**不在任何路径调用** —— 超时不等于放弃（§3.5 末段）。待上游出现明确的放弃语义（如用户中止）时再接。
3. **出站 push notification 注册**：`tasks/pushNotificationConfig/*` 未实现（既有的 P2 缺口，Card 已诚实声明 `pushNotifications: false`）。
4. **不下载产物内容**：只给 `uri`（决策 2）。文本类产物也不内联。
5. **不重试**：轮询期间的 HTTP / 网络失败一律终止轮询并回退快照（§3.2）。对端持续 429 时 Client 不做退避重试。
6. **`message/send` 的 Task 时间戳仍是请求时刻**（决策 4），与 `tasks/get` 的「真实时间」在语义上不同。已在文档写明这是「提交快照生成时刻」。
7. **`percent` 无 `text` 时被丢弃**（§3.6 已知边界，既有行为）。
8. **`tasks/get` 的 `historyLength` 与 `Task.history` 仍不产出**（既有 P2 残余）。
9. **多模态入站（`file` / `data` part）仍被忽略**（既有 P1 缺口）。
10. **轮询参数不可配置**（决策 3）。若日后需要按 peer 调参，需在 `A2aPeer` 上新增字段并设计运营面。
11. **出站轮询会给对端带来额外负载**：每次 Task 响应最多 30 次 `tasks/get`（60s / 2s）。对端自己的限流（含 `scope = api_key` 的 A2A 规则）会约束它；Client 侧不主动降频。
12. **`tasks/resubscribe` 的并发上限**仍是设计级残余（上一批登记），不在本批范围。
13. **不做多轮补全**：对端回 `input-required` 时 Client 只如实回报，不会自动带上补充输入重发。A2A 的 `input-required` 续接需要调用方发起新的 `message/send` 并把 `taskId` 关联回去 —— 属调用方语义，不由传输层代劳（与第 2 条同口径）。

---

## 6. 验收清单

- [ ] Client 收到纯 `Task` 时**不再**把原始 JSON 当回答（反证：移除 Task 分流 → 用例转 RED）
- [ ] 已是终态的 Task **不触发任何轮询请求**
- [ ] `input-required` / `auth-required` 的 Task **不触发轮询**，回答指明「需要补充输入 / 鉴权」
- [ ] 非终态 Task 轮询到终态后，回答含全部产物的 `name` / `mimeType` / `uri`
- [ ] 超时（冻结 `time.monotonic`）后回答含「仍在进行」与 `taskId`
- [ ] `tasks/get` 的 `status.timestamp` 等于 job 的 `updated_at`（不等于请求时刻）
- [ ] `tasks/get` 与 `tasks/resubscribe` 首帧都带 `status.message`（进度文案）
- [ ] `build_a2a_task` 与 `build_a2a_status_update` 的 `status` 形状逐键等价（单一维护点）
- [ ] `Message` 响应的既有解析行为无回归
- [ ] 对端返回 JSON-RPC `error` 时**抛异常**（经 `invoke.py` 记为 `a2a_error`），不再冒充回答
- [ ] `_extract_text_from_response` 的特征化测试**未改动**且全绿
- [ ] `cancel_a2a_peer_task` 具备对称 endpoint 探测与明确的失败契约；代码中**无调用方**（可 grep 验证）
- [ ] 文档三处同步，清点中三条缺口标记关闭
- [ ] 五道质量门全过（`pytest` / `ruff check` / `ruff format` / `make layers-check` / `make openapi-check`）
