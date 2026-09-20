# A2A `tasks/resubscribe`：续播已有生成任务

## 1. 问题

### 1.1 `tasks/resubscribe` 完全缺失

A2A 规范 §7.9 定义该方法：**对端在「`message/stream` 或更早一次 `tasks/resubscribe` 的连接被
中断」之后，重新接回某个仍在进行中的任务的 SSE 流**，前提是 Card 声明
`capabilities.streaming: true`（本平台已为 `true`）。

本平台现状：`tasks/resubscribe` 落在「未实现」分支，一律回 `-32601`
（`docs/guides/a2a.md` §待做、`services/server.py` 的方法白名单）。于是对端一旦断连，
就只能退化为 `tasks/get` 轮询 —— 而任务进度更新本就有现成的推送能力，等于白白丢掉。

### 1.2 合成 `taskId` 不落库，不属于可续播范围

上一批（`2026-09-18-a2a-message-stream-design.md` 决策 5）已定：**`message/stream` 的
`taskId` 是合成的、不落库**，本次流结束后对该 id 调 `tasks/*` 回 `-32001`；若该轮产生了
异步生成任务，真实 job id 经末帧 `status.message.metadata.a2aJobTaskId` 交给对端。

这是本批的前提：`tasks/resubscribe` 的 `params.id` **只接受真实生成任务 id**
（`GenerativeJob.id`）。合成 id 续播需要先落库合成任务并提供可查记录，成本远高于本批价值。

### 1.3 顺带：平台 SSE 端点的四处重复序列

`GenerativeJobService.stream_job_events` 有 4 处重复的
「`expire_all` → 取 job → 序列化 → yield 一帧」序列：初次推送、Pub/Sub 循环内、
Pub/Sub 兜底终查、Redis 不可用的 DB 轮询。既有测试文件
`tests/tenant/generative/test_job_stream_events.py` 的 docstring 明写它**逐条覆盖这 4 条路径，
「使后续提取公共序列时可回归验证」** —— 重建同一套订阅循环是重复劳动且会复制一批已知坑
（`get_message` 必须显式传 timeout 否则非阻塞空转、终态兜底终查、Redis 不可用回退轮询、
收尾必须取消订阅）。故本批把该序列提取为共用 watcher，两个消费方共用。

## 2. 已确认的决策

| # | 决策点 | 选定 |
|---|---|---|
| 1 | 可续播范围 | **只对真实生成任务 id 生效**；合成流式 `taskId` 回 `-32001`；不新增落库合成任务的机制 |
| 2 | 实现方式 | **抽取共用 watcher** 到 `generative/services/job_watch.py`，平台 SSE 与 A2A 订阅共用；既有 13 条特征化测试作安全网 |
| 3 | 流结束条件 | **按规范：开到任务进入终态/中断态**；靠 SSE 心跳保活；另设 **30 分钟安全上限**（到点发一帧真实状态的 `final=true` 收尾，记为对规范的有意偏离，见 §3.5） |
| 4 | 帧去重与进度 | 仅在「映射出的 `TaskState` 或进度指纹变化」时发帧，其余发心跳；进度走 `status.message.parts[].text`，百分比放 `status.message.metadata.percent` |
| 5 | 审计口径 | 任务被取消（`canceled` 终态）记 **`outcome=ok`** + `detail.taskState="canceled"` —— `canceled` 这一 outcome 专指「对端断连」 |
| 6 | `contextId` | 沿用既有判据 `_context_id_from_job_params`：能解析就带、解析不到则**省略该字段**（偏离规范对 `TaskStatusUpdateEvent.contextId` 的必填要求，见 §3.8） |

## 3. 设计

### 3.1 协议契约

- **方法**：`tasks/resubscribe`（与 `message/send` / `message/stream` 共用同一 JSON-RPC 端点）
- **载荷**：规范的 `TaskIdParams` —— `{"jsonrpc":"2.0","id":<id>,"method":"tasks/resubscribe","params":{"id":"<taskId>"}}`
- **响应**：SSE，每帧 `data` 为一个完整的 JSON-RPC 响应对象。规范 §7.2.1 明确
  「`data` 字段的内容由 `message/stream` **与 `tasks/resubscribe`** 共用」，
  故响应形状与 `message/stream` 同构，复用既有 `jsonrpc_result` 与 SSE 帧原语。
- **Card**：`capabilities.streaming` 已为 `true`，无需改动。
- **超限**：与 `message/stream` 同法，在开流之前回 429 + `Retry-After` + JSON-RPC `-32000`。

SSE 帧原语（`sse_frame` / `now_iso` / `SSE_HEARTBEAT_FRAME` / `SSE_HEARTBEAT_SECONDS`）
当前是 `services/server.py` 的模块私有符号，本批移到新文件 `services/streaming.py`，
由 `server.py` 与 `subscription.py` 共同引用 —— 否则订阅模块只能 import 兄弟模块的私有符号，
比移动更差（与 §3.7 的审计调度搬迁同一取舍）。

**心跳常量必须按模块属性引用**（`streaming.SSE_HEARTBEAT_SECONDS`，而非
`from ...streaming import SSE_HEARTBEAT_SECONDS`），使测试只有一个 monkeypatch 点。
既有测试 `test_a2a_server_card.py` 里那处
`monkeypatch.setattr(server_svc, "SSE_HEARTBEAT_SECONDS", 0.01, raising=False)`
随之改为 patch `streaming` 模块（一行改动）。

### 3.2 帧序列

规范对任务生命周期的流给出序列契约（`StreamResponse` 注释）：

> 首帧应为 `Task` 对象，随后是零或多个 `TaskStatusUpdateEvent` 与 `TaskArtifactUpdateEvent`；
> **流应在任务进入 interrupted 或 terminal 状态时结束。**

```
Task(kind=task)                          # 首帧
  ├─ 订阅时已终态 → status-update(终态, final=true)  → 结束
  └─ 未终态 → status-update(final=false)…            # 进度变化时才发
              artifact-update(lastChunk=true)…       # 任务转入终态且有产物时，每个产物一条
              status-update(终态, final=true)        # 收尾
```

产物帧与首帧的分工（避免同一产物在一条流里出现两次）：

- 首帧 `Task` **仅当订阅时已终态**才带 `artifacts`（一帧讲完整段故事）；
- `artifact-update` 帧**仅用于本次订阅期间发生的产出**（即任务在订阅后转入终态时）。

`TaskState` 取值（规范 §6.3）：终态为 `completed` / `failed` / `canceled` / `rejected`；
中断态为 `input-required`。映射沿用既有 `to_a2a_task_state`（未知状态回 `unknown`）。

**本平台的生成任务不会进入中断态**：`GenerativeJobStatus` 只有
`pending` / `running` / `success` / `failed` / `cancelled`，映射后为
`submitted` / `working` / `completed` / `failed` / `canceled` —— 既无 `input-required`，
也无 `rejected`。故订阅流的正常结束只有两种：**任务终态**，或 §3.5 的安全上限。

终态帧的 `status.message` 文本取 §3.3 的 `progress_text`（可能为空则不附该帧的 `message`）：
本方法没有「回答正文」可带，任务的产出就在 `artifact-update` 帧里。

### 3.3 纯逻辑层新增

`miles_portal/tenant/a2a/server.py`（无 ORM / 无 DB）：

```python
def build_a2a_artifact_update(
    *,
    task_id: str,
    context_id: str | None,
    artifact: dict,
    last_chunk: bool = True,
) -> dict
```

产出规范 §7.2.3 的 `TaskArtifactUpdateEvent`：`kind="artifact-update"`、`taskId`、
`contextId`（可选）、`artifact`、`lastChunk`。

`artifact` 直接吃既有 `build_a2a_artifacts` 的**单项产出** —— 它返回的每个元素本就是完整的
`Artifact`，故无需再抽 `build_a2a_artifact`：调用方遍历该列表、逐个包一层事件即可，
`file.uri` 的拼法仍只有一处。

```python
def progress_text(*, progress_message: str | None, percent: int | None) -> str | None
```

进度文案：`progress_message` 非空则用它（它通常已含百分比，如「45% 渲染中」）；
否则仅有 `percent` 时回 `"{percent}%"`；两者皆无回 `None`（不附 `text`）。

```python
def now_iso() -> str   # 自 services/server.py 的 _now 上移
```

`TaskStatus.timestamp` 是协议字段，其取值属纯逻辑层；上移后订阅模块不必为取个时间戳去
import 用例模块。

**既有构造函数的签名放宽**：`build_a2a_status_update`（及其嵌套的
`build_a2a_agent_message`）当前要求 `context_id: str`。为支持 §3.8 的「解析不到则省略」，
把二者的 `context_id` 放宽为 `str | None` 并在为空时省略该字段 —— 与 `build_a2a_task`
既有的「解析不到就省略、不塞空串冒充」同法。对现有调用方（总是传实值）行为不变。

`build_a2a_status_update` 另加 `percent: int | None = None`：非空时写进
`status.message.metadata.percent`。它复用既有的 `metadata.a2aJobTaskId` 那一层
（`message["metadata"]`），两者都在时合并。

```python
def is_terminal_generative_status(status: object) -> bool
```

「该状态是否已终态」，由既有 `is_active_generative_status` 反推而来（后者改为
`not is_terminal_generative_status(...)`，语义与既有测试一字不变）。订阅循环需要正向判据
（`is_terminal` 注入点），用「非 active」表达会把否定藏进参数名里。

### 3.4 共用 watcher

新文件 `miles_portal/tenant/generative/services/job_watch.py`：

```python
async def watch_generative_job(
    *,
    job_id: UUID,
    tenant_id: UUID,
    reload: Callable[[], Awaitable[GenerativeJob]],
    is_terminal: Callable[[GenerativeJob], bool],
    max_seconds: float,
    poll_interval: float = 1.0,
    emit_ticks: bool = False,
) -> AsyncIterator[GenerativeJob | None]
```

接口刻意收窄到**与 SSE、JSON、A2A 全无关**，只吐 `GenerativeJob` 快照；注入点正是两个消费方
唯一不同的地方：

| 参数 | 平台 SSE（`stream_job_events`） | A2A 订阅 |
|---|---|---|
| `job_id` / `tenant_id` | 入参与 `ctx.tenant_id` | 同（频道名由二者拼出，两处同用一个 `RedisKeys` 约定） |
| `reload` | 请求作用域 `db` + `_reload`（`expire_all` 后重取） | `AsyncSessionLocal()` 短开短关 |
| `is_terminal` | 平台 `_TERMINAL` 枚举集 | `is_terminal_generative_status`（纯逻辑层） |
| `max_seconds` | `120`（原样） | `1800` |
| `poll_interval` | `1.0`（原样） | `2.0` |
| `emit_ticks` | `False`（原样：不产刻度） | `True` |

**`None` 刻度（`emit_ticks`）**：为真时，一次「没等到消息」的轮询会产出一个 `None`。
这是订阅侧能发保活帧的**唯一**可行做法：消费方的 `async for` 会一直挂在
`__anext__` 上，若不在空闲时给它一个产出点，它就没有执行机会。之所以不用
`asyncio.wait_for(anext(agen), timeout=…)` 来「超时发心跳」，是因为 `wait_for` 超时会
**取消**那次 `anext`，`CancelledError` 被打进生成器内部、生成器就此关闭 —— 之后再也拿不到
任务更新。

平台侧令 `emit_ticks=False`：它不需要心跳（`message/stream` 的心跳在它自己的轮次循环里做，
`stream_job_events` 只负责发任务帧），且不产刻度才能保证既有 13 条断言逐帧不变。

**顺序严格照搬既有实现**（这是既有测试能原样通过的前提）：

1. `job = await reload()` → `yield job`；
2. 若 `is_terminal(job)` 则**直接结束，不订阅**；
3. 订阅频道（名由 `RedisKeys.generative_job_progress(tenant_id, job_id)` 拼出）；
4. 循环：`msg = await pubsub.get_message(timeout=poll_interval)`；
   - **`timeout` 必须显式传非 0 值**：redis-py 省略时默认 `0.0` 为非阻塞，循环会立刻空转
     打满 CPU（既有测试 `test_every_poll_passes_a_blocking_timeout` 守着这条）；
   - `msg` 为 `message` 类型才 `reload()` 并 yield；
   - 否则若 `emit_ticks` 则 yield `None`；
   - 总时长达 `max_seconds` 退出循环；
5. **兜底终查**：退出循环后若从未 yield 过终态，再 `reload()` 一次，终态则 yield
   （防 Pub/Sub 消息丢失让对端永久等待）；
6. `except Exception`：记 warning + **降级为 DB 轮询**，上限 `max_seconds / poll_interval` 次
   （平台 120 次、A2A 900 次，与既有行为一致），每轮 `reload()` 后 yield 一次快照；
7. `finally`：取消订阅，失败只记 debug（不影响收尾）。

`get_redis` 必须在**函数体内** import：既有测试用
`monkeypatch.setattr("miles_core.infra.redis.get_redis", …)` 替换源模块属性，模块级
`from … import get_redis` 会把替换前的引用固化进来，替换失效后单测会去连真 Redis。

**平台侧 `stream_job_events` 改为该 watcher 的薄封装**：保留其签名与 4 条路径行为
（含「DB 回退路径每轮都发帧、不产刻度」），既有 `test_job_stream_events.py` 的 13 条断言
必须**原样全绿**（本批不做行为变更）。

### 3.5 流结束条件与安全上限

规范的结束条件是「任务进入 interrupted 或 terminal 状态」。本批据此**不设短上限**：
任务未终态就继续推，靠保活帧撑住连接 —— 空闲轮询产出一个刻度（见 §3.4）时，消费方下发
`SSE_HEARTBEAT_FRAME = ": ping\n\n"`（与 `message/stream` 共用该常量）；一次「快照无变化」
的产出同样回一个保活帧，而不是重复帧。**保活节奏即订阅的轮询间隔（2s）**，比
`message/stream` 的 15s 更密 —— 订阅可能持续半小时，连接更不能被中间层掐断，
而代价只是每 2 秒 8 字节。

另设 **30 分钟安全上限**：到点仍未终态则发一帧 `final=true` 的 `status-update` 结束流，
审计 `detail.endedBy="safety-cap"` 并记 warning。该帧的 `state` 取任务当前的**真实映射值**
（通常即 `working`；任务仍为 `pending` 时是 `submitted`）—— 与既有「未知状态回 `unknown`
而非 `completed`」同一原则，不谎报状态。这是**对规范的有意偏离**（规范要求流在
interrupted/terminal 结束），理由是病态任务不应无限占住连接；且 `message/stream` 对
「产物未就绪」已用同一姿态（`working` + `final=true`）收尾，对端本就必须处理它。
偏离与重订阅方式写入 `docs/guides/a2a.md`。

**断连期间的事件不回填**：规范明确「错过的事件是否回填由实现自定」，本平台只发订阅之后的
新事件（首帧 `Task` 即当前快照，足以让对端对齐进度），并在指南写明。

### 3.6 DB 会话与连接占用

A2A 侧**不持有请求作用域的 `db`**：

- 前置校验（解析 id、归属校验）用注入的 `db`；通过后 `await db.commit()` 结束请求级事务、
  归还连接（用 `commit` 而非 `rollback`：同一会话里鉴权依赖已 `flush` 了 API Key 的
  `last_used_at`，`rollback` 会把这笔记账丢掉 —— 与 `open_a2a_stream` 同一取舍）。
- 订阅期间由 watcher 的 `reload` 闭包用 `AsyncSessionLocal()` **短开短关**：30 分钟上限下
  绝不能让一条连接陪跑整段流。

订阅期间若发生非预期异常（典型：任务在流中途被删，租户取数失败），回一帧 `failed` 终态
再收流，并记 `outcome=failed` / `endedBy="failed"` 的流水 —— 与 `message/stream` 的
「error 与 response 同时为空也要回一帧 failed」同一姿态：**绝不让对端等到「流突然断掉却
没有终态帧」**，也绝不让留痕在这条罕见路径上丢失。取消类异常（`GeneratorExit` /
`CancelledError`）必须原样重抛、不进这条兜底，否则会把断连伪装成执行失败。

### 3.7 审计与限流

- **限流**：同一端点在**开流之前**判定，复用既有 `check_a2a_rate_limit`；超限回
  429 + `Retry-After` + JSON-RPC `-32000`（无需改动视图的限流段）。
- **审计**：新增动作 `a2a.tasks.resubscribe`，登记进
  `tenant/audit_log/meta.py` 的 `ACTION_FILTER_OPTIONS`（否则租户在审计页筛不到）。
  - 前置校验失败：`outcome=AUDIT_OUTCOME_FAILED`，`detail.errorCode` 取实际回给对端的错误码
    —— `params.id` 缺失/非法 UUID → `INVALID_PARAMS`（`-32602`）；
    任务不存在 / 不属于该智能体 / 是合成流式 id → `TASK_NOT_FOUND`（`-32001`）。
    与 `message/stream` 前置失败同口径（那一批已把「前置失败不写流水」当作缺陷补过，
    这里一次做对）。
  - 流式终态：复用既有「同步幂等调度 + 脱离取消作用域」机制
    （`schedule_audit` / `_PENDING_AUDITS` / `drain_pending_audits`），
    终态为 `completed` → `outcome=ok`、`failed` → `outcome=failed`；
    对端断连 → `outcome=canceled`。（`rejected` 不适用于本方法 ——
    生成任务不会进入 `rejected` 状态，见 §3.2。）
  - `detail.endedBy`：`"terminal"`（任务终态）/ `"safety-cap"`（30 分钟上限）/
    `"disconnect"`（对端断连）/ `"failed"`（订阅中途的非预期异常，见 §3.6 末）。
  - `detail.taskState`：收流时映射出的 A2A 状态（断连时为「断连前最后一次已知状态」，
    未知则 `unknown`）。
  - **任务被取消（`canceled` 终态）记 `ok`**，`detail.taskState="canceled"` —— 这是合法终态、
    订阅正常走完；`canceled` 这一 outcome 在本设计里专指「对端断连」，混用会让两者不可区分。
- **一处小重构**：把上述审计调度机制从 `a2a/services/server.py` 移到
  `a2a/services/audit.py`（它是审计基础设施，`subscription.py` 要复用）。不移动就只能让
  `subscription → server` 单向依赖，比移动更差。同包内移动、无环；`drain_pending_audits` 的
  import 处（测试）同步更新。

### 3.8 `contextId` 的取舍

规范把 `TaskStatusUpdateEvent.contextId` 与 `TaskArtifactUpdateEvent.contextId` 标为**必填**
（`Task` 的 `contextId` 反而是可选）。本平台 `Task.contextId` 一贯是「解析不到就省略、
不塞空串冒充」（既有测试锁定），解析判据是单一来源
`chat_artifact_sync.conversation_id_from_job_params`（`params.conversation_id` 或
`agent_config._conversation_id`）。

本批选择**沿用同一判据**：能解析就带、解析不到就省略该字段，并把「此处偏离规范的必填要求」
记入 spec 与指南。理由：塞空串冒充会让对端拿到一个假的上下文标识；而能走到
`tasks/resubscribe` 的任务必然由 A2A 发起、必有 `contextId`，实际影响很小。
（另一条可选做法是解析不到就拒绝订阅，但那会把罕见的合法任务挡在门外。）

### 3.9 接口清单

```text
# miles_portal/tenant/a2a/server.py（纯逻辑，无 ORM / 无 DB）
+ build_a2a_artifact_update(...) -> dict          # 规范 §7.2.3
+ progress_text(...) -> str | None
+ is_terminal_generative_status(...) -> bool
+ now_iso() -> str                                 # 自 services/server.py 的 _now 上移
~ is_active_generative_status(...)                # 改为 is_terminal 的取反
~ build_a2a_status_update(..., context_id: str | None, percent: int | None)
~ build_a2a_agent_message(..., context_id: str | None)

# miles_portal/tenant/generative/services/job_watch.py（新增）
+ watch_generative_job(...) -> AsyncIterator[GenerativeJob | None]

# miles_portal/tenant/generative/services/job.py
~ stream_job_events(job_id)                        # 改为 watcher 薄封装，行为不变

# miles_portal/tenant/a2a/services/streaming.py（新增：流式公共原语）
+ sse_frame(payload) / elapsed_ms(started)
+ SSE_HEARTBEAT_FRAME / SSE_HEARTBEAT_SECONDS      # 自 server.py 迁入，按模块属性引用

# miles_portal/tenant/a2a/services/audit.py
+ _PENDING_AUDITS / schedule_audit() / drain_pending_audits()   # 自 server.py 迁入

# miles_portal/tenant/a2a/services/subscription.py（新增）
+ open_task_subscription(db, ctx, agent_id, payload, *, base_url) -> dict | AsyncIterator[str]

# miles_portal/tenant/a2a/services/server.py
- _PENDING_AUDITS / _schedule_audit / drain_pending_audits      # 迁出至 audit.py
- _sse_frame / _now / SSE_HEARTBEAT_* / _elapsed_ms             # 迁出至 streaming.py
~ _parse_task_id / _load_owned_agent_task / _context_id_from_job_params
                                                   # 去掉下划线：订阅模块要用
~ _AUDIT_ACTION_BY_METHOD                          # 不含 tasks/resubscribe（不经 _dispatch）

# miles_portal/tenant/audit_log/meta.py
+ ("a2a.tasks.resubscribe", "A2A 订阅任务更新", None)

# miles_openapi/views/a2a_server.py
~ a2a_jsonrpc                                      # 第三种分流：tasks/resubscribe → StreamingResponse
```

## 4. 测试

**先写、先红**（TDD）。层次与覆盖：

| 层次 | 用例 |
|---|---|
| watcher | 既有 `test_job_stream_events.py` 13 条**原样全绿**（证明平台端点行为未变）＋ 直接测注入式接口（自定义 `max_seconds` / `poll_interval`、`poll_interval` 透传到 DB 回退的 `sleep`） |
| 纯函数 | `build_a2a_artifact_update` 形状（`kind`/`artifact`/`lastChunk`、无 `contextId` 时省略）；`progress_text` 三种取值；`build_a2a_status_update` 在 `context_id=None` 时省略 `contextId`（含嵌套消息） |
| 服务层 | ① 帧序列：`Task` → 去重后的 `status-update` → `artifact-update` → 终态 `final=true`；② 订阅时已终态：`Task`（带 `artifacts`）+ 终态帧后立即结束，**不发** `artifact-update`；③ 重复快照（同状态同进度）被去重；④ 安全上限以「当前真实状态 + `final=true`」收尾（`running` → `working`），审计 `endedBy="safety-cap"`；⑤ 对端断连恰好一条 `canceled` 流水；⑥ 非归属任务与合成 id 回 `-32001` 且各写一条 `failed` 流水；⑦ 「任务被取消」记 `ok` + `detail.taskState="canceled"`；⑧ `contextId` 解析不到时帧里无该字段 |
| API 层 | 视图把 `tasks/resubscribe` 分流为 `text/event-stream`；限流在开流前判出（429 + `Retry-After` + `-32000`）；审计动作已登记进 `ACTION_FILTER_OPTIONS`（`test_domain_meta` 的 `literal_options`） |

每一条新用例都要能**区分对错**（变异/回退后必须红），证据写进实现报告。

## 5. 本批明确不做

- `tasks/pushNotificationConfig/*`（set / get / list / delete）
- **A2A v1.0 迁移**：PascalCase 方法名、去 `kind` 换成员名包装、`TASK_STATE_*` 取值
- 多模态入站：`parts` 的 `file` / `data` 类型（现仅取 `text`）
- `MessageSendParams.configuration`（`blocking` / `acceptedOutputModes` 等）语义
- **合成流式 `taskId` 的落库与续播**（§1.2；需新表/新字段 + 终态后生命周期清理）
- 断连期间事件的**回填**（规范明确 implementation-dependent；只发订阅之后的新事件）
- 非真流路由（`tool_agent` / `flow` / 子智能体 / `a2a_augmented` / `a2a_host`）的逐 token 化
- `watch_generative_job` 被 `miles_portal` 之外的包引用（本次仅两处消费方）

## 6. 影响面

- **对外行为**：新增一个方法；`tasks/resubscribe` 从 `-32601` 变为 SSE 流。**破坏性为零**
  （原先没有任何对端能成功调用它）。
- **内部行为**：`stream_job_events` 有等价重构，既有 13 条特征化测试是回归依据；审计调度
  机制仅换文件位置。
- **运营面**：`adm_rate_limit_rules` 无需迁移；审计页多一个可筛动作。
- **连接占用**：平台 SSE 仍是 120s 上限（不变）；A2A 订阅最长 30 分钟，但 DB 连接为短开短关。
- **待做的重新计数**：`docs/guides/a2a.md`、`docs/features/a2a-interconnect.md`、
  `docs/architecture/technical-design.md` 三处「待做」列表需把本项移除；
  `pushNotificationConfig/*`、v1.0、多模态入站继续留。
