# A2A 外部互联

**状态：** 已实现（登记/引用/宿主 ✅；对外暴露 Card + `message/send` + `message/stream` 流式 + `contextId` 多轮 + `tasks/*` + 产物下载 ✅）  
**PRD 对照：** 模块4 A2A 互联智能体  
**协议：** [A2A Protocol v0.3.0](https://a2a-protocol.org/v0.3.0/specification/) · [a2a.md](../guides/a2a.md)

---

## 1. 背景与目标

**A2A（Agent-to-Agent）** 用于跨厂商、跨平台的智能体互联：登记外部 Agent Card，通过标准 JSON-RPC 调用外部 Agent。

与 **内部协同**（`agt_sub_agent_bindings`）分表、分 Tab、互不替代。

| 模式 | 数据 | 行为 |
|------|------|------|
| **外部登记** | `agt_a2a_peers` | 维护目录、同步 Card |
| **互联宿主** | `agent_type=a2a` + `agt_a2a_peer_bindings` | 对话以调用外部为主 |
| **平台内引用** | `agt_agent_a2a_peer_refs` | custom 本地推理后再增强调外部 |

### 1.1 交付范围

- Peer CRUD、probe、sync-card
- 宿主智能体创建/绑定、trigger_keywords
- custom 智能体 peer_refs + `a2a_invoke_policy`
- `run_a2a_host_chat` / `augment_response_with_a2a`
- 前端：A2A 互联 Tab（外部登记、互联宿主）

### 1.2 交付范围（对外暴露）

- 指定 `custom` 智能体 `config.a2a_publish=true` → 对外 Agent Card 与 JSON-RPC `message/send`
- JSON-RPC 方法：`message/send`、`message/stream`（SSE 真流式）、`tasks/get`、`tasks/cancel`、`tasks/resubscribe`（续播生成任务进度）
- 多租户按智能体寻址；根 `/.well-known/agent-card.json` 仅在唯一发布时 307 别名
- Card 公开（发现元数据），调用端点用该智能体的 X-API-Key；Card 内声明 `securitySchemes` / `security` 供对端发现鉴权要求
- Card 声明 `protocolVersion=0.3` 与 `capabilities.streaming=true`，与线格式（`kind` 判别字段、小写 TaskState）一致
- 对外调用：按 API Key 限流（429 + `Retry-After` + JSON-RPC `-32000`）；每次调用落租户审计 `a2a.*`，超限另落风控事件 `a2a_rate_limit`

### 1.3 明确不做

- `tasks/pushNotificationConfig/*`（现回方法未找到）
- A2A v1.0 迁移（PascalCase 方法名 + 去 `kind` + `TASK_STATE_*` 取值）

---

## 2. 数据模型

### 2.1 表 `agt_a2a_peers`

| 字段 | 说明 |
|------|------|
| `agent_card_url` | Card 拉取地址 |
| `agent_card_json` | 缓存 Card |
| `base_url` | 调用基址 |
| `auth_config` | 认证 JSON：`headers`（任意头）/ `api_key`（X-API-Key）/ `bearer_token`（Bearer），同步 Card 与调用时携带 |
| `status` | pending / active / error / inactive |

### 2.2 表 `agt_a2a_peer_bindings`

互联宿主 → Peer：`trigger_keywords`（逗号分隔关键词命中强制路由）。

### 2.3 表 `agt_agent_a2a_peer_refs`

custom 智能体 → Peer：`trigger_keywords`、`role_hint`。

**宿主约束：** 禁止 `sub_agents` / `kb_ids` / `published_flow_id` 作为主路径。

---

## 3. 运行时

### 3.1 互联宿主

```
POST /agents/{a2a_host_id}/chat
    → run_a2a_host_chat
    → 规则/规划选 Peer
    → invoke_a2a_peer (JSON-RPC message/send)
    → steps: type=a2a_peer
```

### 3.2 custom + peer_refs

```
本地 RAG / 内部协同 / 流程 先执行
    → augment_response_with_a2a
    → config.a2a_invoke_policy:
        rules_then_plan | plan_only | rules_only
    → max_a2a_calls_per_turn (默认 2)
```

Peer 须 `status=active` 且 Card 有效。

### 3.3 出站行为（Client → 外部 Peer）

`invoke_a2a_peer` 发 `message/send`，响应按 **`error` → `Task` → 文本** 的固定顺序判读：

- 顶层 JSON-RPC `error` → **调用失败**（抛 `BadRequestError`，`steps[].type = "a2a_error"`），错误消息不再冒充回答；HTTP ≥ 400 才继续试下一个 endpoint 形态，一旦对端按 JSON-RPC 应答即停止探测。
- `result.status.state` 存在（`Task`）→ **有限轮询** `tasks/get`：间隔 2s、总上限 60s（常量，不设配置项），先睡再查；端点与 `message/send` 逐位对称探测。
- 已是「停止轮询态」→ 直接渲染，**不发任何 `tasks/get`**。停止轮询态 = 终态 `completed` / `failed` / `canceled` / `rejected` ∪ 中断态 `input-required` / `auth-required`（对端在等补输入或凭证，继续等只是白等；`input-required` 的提问在 `status.message` 里，一并带回）。
- 终态产物只渲染**引用清单**（`artifactId` / `name` / `mimeType` / `uri`），**不下载内容**；缺 `uri` 写「（无下载地址）」。
- 失败信号一律终止轮询并回退「最后一次已知状态 + `taskId`」快照（不重试）：超时、HTTP ≥ 400、网络异常 / 非 JSON、对端返回 JSON-RPC `error`（`-32601` 是最典型的「不支持 `tasks/get`」，但实际是**任意** `error` 都回退）；「响应形状不认识」不算失败，继续等。
- 轮询会给对端带来额外负载（每次 Task 响应最多约 30 次 `tasks/get`），受对端 `scope = api_key` 限流约束；Client 不主动降频。
- 出站 `tasks/cancel`（`cancel_a2a_peer_task`）**只补能力、不自动调用**：超时 ≠ 放弃，产物属对端用户。

---

## 4. API

### 4.1 Peer `/api/v1/a2a/peers`

```
GET  /a2a/peers/meta
GET  /a2a/peers
POST /a2a/peers
POST /a2a/peers/probe              # 探测连通性
GET/PATCH/DELETE /a2a/peers/{id}
POST /a2a/peers/{id}/sync-card
```

### 4.2 智能体

```
GET  /agents?agent_type=a2a       # 互联宿主列表
POST /agents/{id}/chat            # 宿主或 custom 增强
```

创建宿主：`agent_type=a2a`，绑定 peers 在 agent body 或专用表单。

### 4.3 对外暴露（本平台作 Server，`/api/v1/open`）

```
GET  /a2a/agents/{agent_id}/.well-known/agent-card.json   # 公开，仅 config.a2a_publish=true 命中
POST /a2a/agents/{agent_id}                               # JSON-RPC message/send | message/stream | tasks/get | tasks/cancel | tasks/resubscribe，X-API-Key
GET  /a2a/agents/{agent_id}/tasks/{task_id}/artifacts/{attachment_id}   # 任务产物，X-API-Key
GET  /.well-known/agent-card.json                         # 全平台唯一发布时 307；否则 404
```

发布门槛：`agent_type=custom` + `status=enabled` + `config.a2a_publish=true`；未发布的智能体，Card GET 与「不存在」同回 404（根别名不按某个智能体判可见性，而是只看候选集合：只有 `config.a2a_publish=true` 的智能体入候选，恰一个才 307、否则 404；调用端点的未发布行为见下句）。
JSON-RPC 协议级错误（解析 / 方法 / 参数）回 HTTP 200 + `error` 信封；业务异常按域映射（`tasks/*` 的 401/403/404 → `-32001`，其余域的 401/403/404 与 400 → `-32602`，409/5xx → `-32603`）。未预期故障按方法分口径：`tasks/get` / `tasks/cancel`（RPC 路径）回 HTTP 500 平台信封，`message/send` 中 `run_published_agent_chat` 抛出的非 `AppError` 仍被吞成 HTTP 200 + `-32603`（旧口径；该 `try` 之外的前置与信封组装阶段的非 `AppError` 逸出后仍是 500），`message/stream` 与 `tasks/resubscribe` 的流内故障以终态帧收流。未发布智能体在 `message/send` / `message/stream` / `tasks/resubscribe` 的前置校验里回 HTTP 200 + `-32602`，不是 404。
Card 含 `securitySchemes`（`apiKey` · `in: header` · `name: X-API-Key`）与 `security`，声明的是调用端点要求；Card GET 本身公开。
多轮：`message.contextId` → `ChatRequest.conversation_id`（LangGraph `thread_id` 后缀），响应 `Message.contextId` 回显；未带时服务端生成。
Task：`message/send` 产生生成任务时回 `Task`（`id` 即平台 job id，状态照实映射；产物未就绪时这条是**提交快照**，`status.timestamp` 用请求时刻，因上游只给出 `{id, kind, status}`）；`tasks/get` 查状态并在成功时附 `Task.artifacts`，其 `status.timestamp` 取任务 `updated_at` 的**真实状态时间**、`status.message` 带进度文案与 `metadata.percent`（无进展可说则不附该键）；`tasks/cancel` 取消（不属于该智能体 / 不存在 `-32001`、已结束 `-32002`）。
产物下载走鉴权端点（平台不暴露签名 URL），授权限「该智能体 · 该任务 · 该产物」。`tasks/resubscribe` 以真实生成任务 id 续播进度流（首帧 `Task`、变化帧 `status-update`、终态前 `artifact-update`、空闲保活帧、30 分钟安全上限）；`pushNotificationConfig/*` 未实现，回 `-32601`。
流式：`message/stream` 与其余方法共用同一 URL，按 `method` 分流返回 `text/event-stream`。首帧 `Task(working)`、中间帧 `status-update` 增量、末帧 `status-update(final=true)` 带完整回答；合成 `taskId` 不落库（流已给终态，无需再 `tasks/get`），生成任务 id 经 `status.message.metadata.a2aJobTaskId` 交接；合规拦截 `rejected`、执行失败 `failed`。前置校验失败回普通 JSON，不进入 SSE。

---

## 5. 前端

| 组件 | 功能 |
|------|------|
| `A2aAgentsTab` | A2A 互联 Tab 容器 |
| `A2aPeersPanel` | 外部登记列表 |
| `A2aHostFormDialog` | 互联宿主表单 |
| `AgentFormStepContent` | custom 引用外部 Peer（第 4 步） |

工作台：`/workbench/agents` → Tab「A2A 互联」。

---

## 6. 后端文件清单

```
backend/packages/miles-portal/src/miles_portal/tenant/a2a/models.py
backend/packages/miles-portal/src/miles_portal/tenant/a2a/views/peers.py
backend/packages/miles-portal/src/miles_portal/tenant/a2a/card_client.py
backend/packages/miles-portal/src/miles_portal/tenant/a2a/server.py           # 对外 Card / JSON-RPC 纯逻辑
backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/server.py  # 发布门槛、Card 组装、RPC 分发
backend/packages/miles-portal/src/miles_portal/tenant/a2a/invoke.py
backend/packages/miles-portal/src/miles_portal/tenant/a2a/services/
backend/packages/miles-openapi/src/miles_openapi/views/a2a_server.py          # 公开路由
```

---

## 7. 测试计划

1. probe + sync-card → status active
2. 创建 a2a 宿主 + binding → chat 调外部（mock Card）
3. custom + peer_refs + trigger_keywords 命中 → 强制 Peer
4. inactive peer → 跳过或报错
5. 对外 Card：未发布 404 / 已发布返回 `additionalInterfaces`（0.3 形状，含主 `url` 的接口项）；多技能包映射 `skills`；声明 `securitySchemes` 且头名与实际鉴权一致
6. 对外 RPC：`message/send` 正常回信封；缺文本 / 未知方法 / 非 JSON-RPC 各自错误码
7. 根别名：唯一发布 307、0 或 >1 → 404
8. 多轮：带 `contextId` → 作 `conversation_id` 并回显；缺省时生成；超长回 `-32602`
9. Task：产生生成任务时 `message/send` 回 `Task`；`tasks/get` 映射状态；`tasks/cancel` 取消；不存在 / 已结束各自错误码
10. 产物：`tasks/get` 成功时 `artifacts` 指向鉴权下载端点；跨智能体 / 非本任务产物一律 404
11. 流式：首帧 `Task` + 中间帧增量 + 末帧 `completed` 带全文；非真流路由仅首帧 + 末帧；合规拦截 `rejected`、执行异常 `failed`；生成任务末帧 `working/final` 带 `metadata.a2aJobTaskId`；前置失败保持 `application/json`；客户端断连即取消对话任务

---

## 8. 参考

- [a2a.md](../guides/a2a.md)
- [platform-agents.md](./platform-agents.md) — 内部协同对比
- [README.md §概念速查](../README.md) — 三 Tab 语义
