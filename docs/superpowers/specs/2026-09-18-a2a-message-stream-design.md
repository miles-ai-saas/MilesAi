# A2A `message/stream` 真流式与协议版本声明修正

- 状态：设计已确认，待写实施计划
- 日期：2026-09-18
- 前序：同日「A2A `Task.artifacts` 产物下载闭环」（已提交 `0b46423f`）；本次接续 A2A 对外 Server 的剩余项

## 1. 问题

### 1.1 `message/stream` 完全缺失

A2A Server 现支持 `message/send` / `tasks/get` / `tasks/cancel`（`miles_portal/tenant/a2a/services/server.py:365`），
但 `message/stream` 回 `-32601`，Card 里 `capabilities.streaming` 写死 `False`（`miles_portal/tenant/a2a/server.py:147`）。

标准 A2A 客户端在 `streaming=false` 时会走「非流式兜底」，对端拿不到增量；对长回答尤其明显。

同时，平台**已有真 token 流式链路**，只是没有接到 A2A 上：

| 环节 | 位置 | 现状 |
|---|---|---|
| 增量回调类型 | `miles_ai/integrations/langchain/chat_models.py:30` | `OnDelta = Callable[[str], Awaitable[None]]` |
| 逐 chunk 触发 | `miles_ai/integrations/litellm/adapter.py:199-208` | `on_delta(piece)`，`piece` 是**本片增量**（不聚合） |
| 对话入口 | `miles_portal/tenant/agents/services/agent/chat_entry.py:33-37` | `AgentService.chat(..., on_delta=...)` 已支持 |
| 已接的路由 | `chat_rag.py:211`（`direct_chat`）、`chat_rag.py:372/400`（`rag` / `rag_linear`） | 真流 |
| 未接的路由 | `tool_agent` / `flow` / 子智能体 / `a2a_augmented` / `a2a_host` | 忽略 `on_delta` |
| 现有消费者 | `miles_portal/tenant/agents/ws/chat.py:109-113` | WS 侧已用 `on_delta` 推 `chat.delta` |

### 1.2 协议版本声明与实现不一致（实测）

Card 声明 `protocolVersion: "1.0"`（`miles_portal/tenant/a2a/server.py:27`），但方法名与全部 payload 形状都是
**v0.3 风格**。对照 A2A 规范两版：

| 维度 | v0.3.0 | v1.0.0 | 本仓库现状 |
|---|---|---|---|
| JSON-RPC 方法名 | `message/send` / `message/stream` / `tasks/get` / `tasks/cancel` | `SendMessage` / `SendStreamingMessage` / `GetTask` / `CancelTask` | v0.3 风格 |
| 多态判别 | 对象内 `kind` 字段（`{"kind":"task"}`） | `kind` **已移除**（规范 A.2.1 写明「不应再发出」），改用成员名包装（`{"task":…}` / `{"statusUpdate":…}`） | v0.3 风格（`build_a2a_task` 产 `"kind": "task"`） |
| 文本 part | `{"kind":"text","text":…}` | `{"text":…}` | v0.3 风格 |
| 文件 part | `{"kind":"file","file":{…}}` | `{"raw":…,"filename":…,"mediaType":…}` 或 `{"url":…}` | v0.3 风格 |

问题不在于「选了哪一版」，而在于**声明的是 1.0、实现的是 0.3**：按 1.0 调用的客户端会拿 `-32601`，且会把
`kind` 当未知字段。修一行常量即可让声明自洽；全面迁到 1.0 是另一批工作量（见 §5）。

### 1.3 本批要解决的

1. 声明修正为 `"0.3"`，使 `protocolVersion` 与实现一致。
2. 新增 `message/stream`：同一端点、SSE 传输，`direct_llm` / `rag` / `rag_linear` 路由逐 token 下发，
   其余路由以终态帧一次性下发；Card 声明 `streaming=true`。

## 2. 已确认的决策

| # | 决策点 | 选定 |
|---|---|---|
| 1 | 交付边界 | 协议兼容 + 真流（direct/RAG 真流，其余路由一次性下发 + `final` 收尾）；**不含** `tasks/resubscribe` |
| 2 | 出站合规与流式的冲突 | 事后审计：token 照流，收尾照常 `check_output`；命中拦截则补发失败终态并落拦截日志。与 WS 侧同语义（先流后扫） |
| 3 | 版本声明 | Card 改声明 `"0.3"`，本批新增事件用 `kind` 风格；v1.0 迁移另开一批 |
| 4 | 增量事件形状 | `status-update` + `status.message.parts[].text` 携带**本片增量**；收尾 `status-update(completed, final=true)` 的 `status.message` 带**完整回答** |
| 5 | 流式任务身份 | 合成 `taskId` 不落库；流结束后对该 id 调 `tasks/get` 回 `-32001`；本轮产生异步生成任务时经 `status.message.metadata` 提供真实 job id |

## 3. 设计

### 3.1 协议版本声明修正

`A2A_PROTOCOL_VERSION` 由 `"1.0"` 改为 `"0.3"`。该常量同时喂给 Card 的 `protocolVersion` 与
`supportedInterfaces[].protocolVersion`，改一处即两处一致。

不改方法名与 payload 形状（它们本就是 0.3）。理由是迁移到 1.0 会牵动**出站**侧（`a2a/client.py` 用
`message/send`、`card_client.py` 解析 Card、`invoke.py`）以及全部 Card/事件/测试，与本批「把流式接上」正交，
混做会让回滚粒度变粗。

### 3.2 传输与端点分流

**不新增路由**：v0.3 里 `message/stream` 与 `message/send` 共用一个 URL（`POST /api/v1/open/a2a/agents/{agent_id}`）。

视图层（`miles_openapi/views/a2a_server.py`）在解析 JSON 后按 `method` 分流：

- `message/stream` → `StreamingResponse`，`media_type="text/event-stream"`；
- 其余 → 现有 `JSONResponse` 路径不变。

SSE 响应头沿用平台既有约定（见 `miles_portal/tenant/generative/views/jobs.py:97-101`）：
`Cache-Control: no-cache`、`Connection: keep-alive`、`X-Accel-Buffering: no`。

**返回类型须显式**：路由函数标注 `-> Response`。FastAPI 对 `Response` 子类不做 response model 推断（`JSONResponse`
与 `Response` 同属 `Response` 子类，故两者生成的 OpenAPI 200 响应形状一致）。此处不引入新 schema，
openapi 快照**不应变化**。若写 `JSONResponse | StreamingResponse` 联合则会被当作模型推断，故不采用。

**前置失败不进 SSE**：未发布智能体、`message.parts` 非法、`contextId` 过长，仍回 **HTTP 200 + JSON-RPC error
信封 + `application/json`**，与 `message/send` 的现有错误路径一致。理由：SSE 一旦开始，HTTP 状态与
`Content-Type` 已定，后续错误只能走流内终态事件，对端在 `Content-Type: text/event-stream` 上解析错误信封反而更难处理。

为此用例层导出一个「可能是错误信封、可能是生成器」的入口：

```
open_a2a_stream(db, ctx, agent_id, payload, *, base_url) -> dict | AsyncIterator[str]
```

- 返回 `dict` = 前置校验失败，视图层按普通 JSON 返回；
- 返回异步迭代器 = 校验通过，视图层包成 `StreamingResponse`。

### 3.3 事件序列

每帧 SSE `data:` 是一个**完整的 JSON-RPC 成功信封**（`{"jsonrpc":"2.0","id":<原请求 id>,"result":<…>}`），
`result` 为 v0.3 的 `SendStreamingMessageResponse`。

```jsonc
// 1) 开场：Task（规范要求 Task 生命周期流以 Task 开头）
{"jsonrpc":"2.0","id":1,"result":{
  "kind":"task","id":"<合成 taskId>","contextId":"<contextId>",
  "status":{"state":"working","timestamp":"2026-09-18T09:00:00+00:00"}}}

// 2) 中间帧 × N：增量文本（仅真流路由产生）
{"jsonrpc":"2.0","id":1,"result":{
  "kind":"status-update","taskId":"<合成 taskId>","contextId":"<contextId>",
  "status":{"state":"working","timestamp":"…",
            "message":{"kind":"message","role":"agent","messageId":"<uuid4>",
                       "taskId":"<合成 taskId>","contextId":"<contextId>",
                       "parts":[{"kind":"text","text":"<本片增量>"}]}},
  "final":false}}

// 3) 收尾帧：终态 + 完整回答
{"jsonrpc":"2.0","id":1,"result":{
  "kind":"status-update","taskId":"<合成 taskId>","contextId":"<contextId>",
  "status":{"state":"completed","timestamp":"…",
            "message":{"kind":"message","role":"agent","messageId":"<uuid4>",
                       "taskId":"<合成 taskId>","contextId":"<contextId>",
                       "parts":[{"kind":"text","text":"<完整回答>"}]}},
  "final":true}}
```

要点：

- `contextId` **始终存在**：请求未带 `message.contextId` 时服务端生成一个（与 `message/send` 同策略，见
  `services/server.py:220`），故每帧都带 `contextId`。
- 末帧 `status.message` **必须**带完整回答，且文本取 `response.answer`（权威值），**不取中间帧增量拼接** ——
  回答以对话链路的最终产出为准（它已过 Hook 改写等环节），拼接只在两者恰好一致时才是同一串。
- 末帧带全文的代价（明确记录）：若对端把 `status.message` 当成「追加渲染」，会把回答显示两遍。选该形状是为
  「丢帧也能补全」，规范并未定义 `status.message` 的追加语义（它是独立 `Message`，不是 artifact chunk），
  故按「新增一条消息」处理是对端应有的行为。对接文档中写明该点。
- `final=true` 即「本流结束」，不等于「任务终态」——规范允许 `final=true` 搭配非终态（官方 SDK 示例用
  `input-required + final=True`）。§3.5 的生成任务接续正依赖这一点。
- 中间帧的 `status.message.messageId` 每帧新生成（`uuid4`），不做去重合并；对端按 `taskId` 关联即可。
- 增量片直接透传上游 token，**不聚合、不改写**（合规按 §3.6 事后处理）。

### 3.4 事件生成机制

在 `miles_portal` 用例层实现：起一个 `asyncio.Task` 跑 `AgentService.chat(..., on_delta=cb)`，
`cb` 把增量 `put` 进 `asyncio.Queue`；生成器循环 `await queue.get()` 出帧，任务结束后排空队列并以哨兵收尾。

- 队列要有界（如 `maxsize=64`）并让 `cb` 在满时 `await`（即对上游形成背压），否则对端慢消费 + 长回答会让
  队列无界增长。
- `chat` 抛异常时，生成器捕获并出**终态帧**（见 §3.6），不把异常抛给 ASGI 层（那时响应头已发出，只会得到断流）。
- 客户端断连：`StreamingResponse` 被取消时，须 `cancel()` 该 `asyncio.Task`，否则对话任务与 LLM 调用会继续
  跑到结束才释放（白烧 token）。

### 3.5 合成 taskId 与异步生成任务接续

`taskId` **必须**在流开始时确定（首帧就要发 `Task`），而本轮是否产生活跃生成任务只有跑完才知道。故不把两者
强行合一：

- 纯文本对话（无活跃生成任务）：末帧 `state="completed"`，`final=true`。合成 id 不落库；
  流结束后对它调 `tasks/get`（或 `tasks/cancel`）回 `-32001`。文档写明「`final=true` 已给出终态，无需再查」。
- 本轮产生活跃生成任务（复用既有 `_first_active_job`：带 `id` 且 `is_active_generative_status` 为真）：
  末帧 `state="working"`、`final=true`，并在该帧 `status.message.metadata.a2aJobTaskId` 放入真实 job id。
  对端据此转向 `tasks/get`（job id 是**已落库**的真实任务，可查到状态与 `Task.artifacts`）。

`metadata` 是 A2A `Message` 的既有扩展位，放一个平台自有键不破坏线格式。

选「不落库合成 id」而非新增任务表的代价（明确记录）：对端若在流结束后仍对**合成 id** 调 `tasks/get`，会得到
`-32001`；但流式场景下对端已从终态帧拿到完整回答，且生成任务有独立可查的 job id，故实际不影响正确性。

### 3.6 错误与终态映射

| 情况 | 终态帧 |
|---|---|
| 输入合规拦截（`BadRequestError` 且含敏感词） | `state="rejected"` + 可读原因 |
| 出站合规拦截（回答已流出后才发现） | `state="rejected"` + 原因；拦截日志照常落库 |
| 其他执行异常 | `state="failed"` + 原因；本平台侧 `logger.exception` 留栈 |

- 选 `rejected` 而非 `failed`：v0.3 `TaskState.rejected` 的语义是「智能体拒绝该任务、不会继续处理」，与合规
  拦截一致；`failed` 留给真正的执行失败。
- 出站合规拦截时 token **已经出网**，不可追回。这是决策 2 明确接受的代价，与 WS 侧（先发 `chat.delta` 再
  在收尾跑 `check_output`）语义一致。拦截日志（`ComplianceInterceptLog`）与
  `AgentChatCall.status="blocked"` 照常落库，审计不缺。
- 错误原因走 `str(exc)` 而非完整内部栈；栈只留在平台日志。
- 终态帧里的文本是**已产出部分**（若有）还是空：保持已产出部分，便于对端展示「部分回答 + 被拦截」。

`AFTER_CALL` Hook 与 `AgentChatCall` 调用记录仍在 `AgentService.chat` 的收尾路径 `_complete_chat_turn` 内落库
（`chat_turn.py:52`），流式不改变该路径。

### 3.7 流式下的 DB 会话

- 视图层用注入的 `db` 做**前置校验**（加载已发布智能体、解析参数）；
- SSE 生成器内部**自开 `AsyncSessionLocal()`** 跑整轮对话（与 WS 侧 `agents/ws/chat.py:114` 的
  `_run_chat_turn` 同法）。

理由：整轮对话要在流式期间反复读库，并在末尾 `commit`（成功收尾写调用记录、失败收尾写 blocked 记录）。
依赖 `get_db` 的回收时序在流式响应下不可靠，而 `AsyncSessionLocal` 的生命周期由生成器自己控制。

`TenantContext` 是纯数据（`UUID` / `frozenset` / `str`，见 `deps_api_auth.py:49-57`），跨会话使用安全。

### 3.8 Card 与文档

- `capabilities.streaming`：`False` → `True`。
- `docs/guides/a2a.md`：方法表补 `message/stream`；撤掉「`message/stream` 未实现」「`capabilities.streaming=false`」
  两处表述；补事件序列与终态语义；待做补 `tasks/resubscribe`、`pushNotificationConfig/*`、**v1.0 迁移**、多模态入站。
- `docs/features/a2a-interconnect.md`：状态行「已实现」段补 `message/stream`；「明确不做」只留真未做项。
- `docs/architecture/technical-design.md`：技术栈表中 A2A 一行同步。
- 前端本批不动（Card 展示无需改）。

## 4. 测试

**纯逻辑层**（`miles_portal/tenant/a2a/server.py`，无 DB）：

- `build_a2a_stream_task(...)` / `build_a2a_status_update(...)` 的形状断言：
  首帧 `kind="task"` + `state="working"`；中间帧 `final=False` 且 `status.message.parts[0].text` 为传入增量；
  末帧 `final=True`；`metadata` 带/不带 `a2aJobTaskId` 两种。
- JSON-RPC 信封：帧内 `id` 与原请求一致。

**用例层**（`open_a2a_stream`）：

- 未发布智能体 / `parts` 非法 / `contextId` 过长 → 返回 `dict` 错误信封（不是生成器）；
- 真流路由（`direct_llm` 或 `rag`）→ 首帧 `task` + ≥1 中间帧 + 末帧 `completed/final`；断言末帧文本为
  `response.answer`（**不**断言「末帧 = 中间帧拼接」——回答以 `response.answer` 为准，两者未必逐字相等，
  把拼接当不变量会让测试对上游改动过敏）；
- 非真流路由（如 `flow`）→ 首帧 `task` + 末帧 `completed/final`（无中间帧），末帧带全文；
- 输入合规拦截 → 末帧 `rejected`；
- 执行异常 → 末帧 `failed`；
- 本轮产生活跃生成任务 → 末帧 `working/final=true` 且 `metadata.a2aJobTaskId == <job id>`。

**API 层**（`tests/api/test_a2a_server_api.py`）：

- `POST` 带 `method="message/stream"` → `Content-Type: text/event-stream`，逐帧可解析为 JSON-RPC 信封；
- 前置失败 → `application/json` + `error` 信封（不进 SSE）；
- **回归**：`message/send` 行为不变（回 `Message` / `Task`）；`tasks/get` / `tasks/cancel` 不变。

**Card 层**：

- `capabilities.streaming is True`；
- `protocolVersion == "0.3"`（Card 与 `supportedInterfaces[0]` 两处）。

**质量门**：`make lint-backend format-check-backend layers-check openapi-check test-backend`。
预期 openapi 快照**无变化**（不新增路由与 schema）——若变化即说明返回类型标注引入了推断，须回到 `-> Response`。

## 5. 本批明确不做

- `tasks/resubscribe`（续播已有任务；与 `message/stream` 共用 SSE 机制，但是独立方法）
- `tasks/pushNotificationConfig/*`
- **v1.0 迁移**：PascalCase 方法名、去 `kind` 换成员名包装、文本/文件 part 形状（新版规范 A.2.1 的破坏性变更）
- 多模态入站：`parts` 的 `file` / `data` 类型（现仅取 `text`）
- 非真流路由（`tool_agent` / `flow` / 子智能体 / `a2a_augmented` / `a2a_host`）的逐 token 化
- `MessageSendParams.configuration`（`blocking` / `acceptedOutputModes` 等）：请求里带了也忽略，不做语义
- A2A 专用审计维度与限流（现复用通用访问日志与限流中间件）

## 6. 影响面

| 文件 | 改动 |
|---|---|
| `miles_portal/tenant/a2a/server.py` | `A2A_PROTOCOL_VERSION` → `"0.3"`；`capabilities.streaming` → `True`；新增流式事件的纯构造函数 |
| `miles_portal/tenant/a2a/services/server.py` | 新增 `open_a2a_stream`（前置校验 + 生成器）、事件编排、终态映射 |
| `miles_openapi/views/a2a_server.py` | `method` 分流；`message/stream` 返回 `StreamingResponse` |
| `tests/tenant/a2a/test_a2a_server_card.py` | Card 两处断言 + 流式事件形状用例 |
| `tests/api/test_a2a_server_api.py` | SSE 端到端用例 + `message/send` 回归 |
| `docs/guides/a2a.md`、`docs/features/a2a-interconnect.md`、`docs/architecture/technical-design.md` | 见 §3.8 |

不新增数据库模型、不新增迁移、不新增依赖。
