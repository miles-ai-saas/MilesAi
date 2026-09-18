# A2A 外部互联

**状态：** 已实现（登记/引用/宿主 ✅；对外暴露 Card + `message/send` + `contextId` 多轮 + `tasks/*` ✅）  
**PRD 对照：** 模块4 A2A 互联智能体  
**协议：** [A2A Protocol v1.0](https://a2a-protocol.org/v1.0.0/specification/) · [a2a.md](../guides/a2a.md)

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
- JSON-RPC 方法：`message/send`、`tasks/get`、`tasks/cancel`（生成任务的生命周期）
- 多租户按智能体寻址；根 `/.well-known/agent-card.json` 仅在唯一发布时 307 别名
- Card 公开（发现元数据），调用端点用该智能体的 X-API-Key；Card 内声明 `securitySchemes` / `security` 供对端发现鉴权要求

### 1.3 明确不做

- `message/stream` 真流式（Card 声明 `streaming=false`）
- `tasks/resubscribe`、`tasks/pushNotificationConfig/*`（现回方法未找到）
- `Task.artifacts` 产物下载（产物是平台附件，对端无凭证取回）
- A2A 专用审计/限流（复用通用能力）

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
POST /a2a/agents/{agent_id}                               # JSON-RPC message/send | tasks/get | tasks/cancel，X-API-Key
GET  /.well-known/agent-card.json                         # 全平台唯一发布时 307；否则 404
```

发布门槛：`agent_type=custom` + `status=enabled` + `config.a2a_publish=true`；未发布与不存在同回 404。
JSON-RPC 协议级错误（解析 / 方法 / 参数）回 HTTP 200 + `error` 信封，执行异常回 `-32603`。
Card 含 `securitySchemes`（`apiKey` · `in: header` · `name: X-API-Key`）与 `security`，声明的是调用端点要求；Card GET 本身公开。
多轮：`message.contextId` → `ChatRequest.conversation_id`（LangGraph `thread_id` 后缀），响应 `Message.contextId` 回显；未带时服务端生成。
Task：`message/send` 产生生成任务时回 `Task`（`id` 即平台 job id，状态照实映射）；`tasks/get` 查状态、`tasks/cancel` 取消（不存在 `-32001`、已结束 `-32002`）。`message/stream` 与 `tasks/resubscribe` / `pushNotificationConfig/*` 未实现，回 `-32601`。

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
5. 对外 Card：未发布 404 / 已发布返回 `supportedInterfaces`；多技能包映射 `skills`；声明 `securitySchemes` 且头名与实际鉴权一致
6. 对外 RPC：`message/send` 正常回信封；缺文本 / 未知方法 / 非 JSON-RPC 各自错误码
7. 根别名：唯一发布 307、0 或 >1 → 404
8. 多轮：带 `contextId` → 作 `conversation_id` 并回显；缺省时生成；超长回 `-32602`
9. Task：产生生成任务时 `message/send` 回 `Task`；`tasks/get` 映射状态；`tasks/cancel` 取消；不存在 / 已结束各自错误码

---

## 8. 参考

- [a2a.md](../guides/a2a.md)
- [platform-agents.md](./platform-agents.md) — 内部协同对比
- [README.md §概念速查](../README.md) — 三 Tab 语义
