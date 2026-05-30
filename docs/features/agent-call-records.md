# 智能体对话调用记录

**日期：** 2026-05-29  
**状态：** P0–P3 与 P2 会话持久化已实现  
**PRD 对照：** 模块4 智能体管理 · 运维配置「调用统计、日志记录」  
**架构：** [platform-agents.md](./platform-agents.md) · [agent-chat-websocket.md](./agent-chat-websocket.md) · [realtime-transport-design.md](../architecture/realtime-transport-design.md)

---

## 1. 背景与目标

对话工作台右侧「调用记录」Tab 提供**按智能体维度、跨会话、可检索**的对话调用流水，供运维排障、用量对账与合规审计。

**策略：先实现业务层调用记录（PG 领域表）；OpenTelemetry 作为后续可选增强，v1 不接入。**

### 1.1 与 Trace / 统计的边界

| Tab | 时间范围 | 视角 | 核心问题 |
|-----|----------|------|----------|
| **Trace** | 当前浏览器会话 | 开发调试 | 这一轮怎么执行的？`steps` JSON 与 `trace_id` |
| **调用记录** | 该智能体全部历史（服务端） | 运维 / 合规 | 谁在什么时候调用了什么？成功还是失败？ |
| **统计** | 近 N 天聚合 | 运营 | 会话数、消息数、活跃用户等趋势 |

```text
一轮 chat 回合
    → Trace Tab：本地 chat-sessions 存 steps（即时调试）
    → 调用记录：服务端写 agt_agent_chat_calls（持久流水）
    → 统计 Tab：从 agt_agent_chat_calls 聚合（与流水同口径）
```

### 1.2 交付范围（分阶段）

| 阶段 | 内容 |
|------|------|
| **P0** | 建表 + `AgentService.chat` 写入 + 列表 API + 工作台表格 UI |
| **P1** | 详情弹窗 + `GET /agents/{id}/stats` 真实聚合 + `ModelUsageLog` 关联 `agent_id` |
| **P2** | 会话服务端持久化 + 完整 steps 落库 + 列表/详情 API + 本地合并同步 |
| **P3** | 合规 `blocked` 专项筛选；`trace_id` 关联 Hook / 工具日志 |

### 1.3 明确不做（v1）

- **CSV 导出**
- 每个编排节点各自写调用记录表（避免与 Trace、工具日志重复）
- 完整 `steps` 默认落 PG（体积大、含敏感内容）
- 跨智能体全局调用大盘（归属监控域 `/monitor`）
- **OpenTelemetry 接入**（见 §8；后续有需要再立项）
- OpenAPI 第三方 WS 调用流水（WS 仅工作台，见 agent-chat-websocket）

---

## 2. 数据模型

### 2.1 表 `agt_agent_chat_calls`

**一行 = 一轮对话**（一次 `chat.send` / `POST …/chat` 的完整回合，含子 Agent、工具、RAG 等整条链路）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | 主键 |
| `tenant_id` | UUID | 租户隔离 |
| `agent_id` | UUID | 目标智能体 |
| `conversation_id` | VARCHAR(128) | 与前端 `session.id` / WS query 一致 |
| `trace_id` | VARCHAR(64) NULL | HTTP 中间件 `X-Trace-Id`，便于关联 Hook / 工具日志 |
| `actor_user_id` | UUID NULL | 工作台操作者 |
| `status` | VARCHAR(16) | `success` \| `failed` \| `blocked`（合规拦截） |
| `route` | VARCHAR(32) | 执行路径：`a2a_host` \| `subagent` \| `flow` \| `rag` \| `tool_agent` \| `direct_llm` 等 |
| `query_preview` | TEXT | 用户输入摘要（如前 200 字） |
| `answer_preview` | TEXT | 回复摘要 |
| `latency_ms` | INTEGER | 整轮耗时 |
| `prompt_tokens` | INTEGER | 该轮 LLM prompt Token 合计 |
| `completion_tokens` | INTEGER | 该轮 LLM completion Token 合计 |
| `step_count` | INTEGER | 编排步数 |
| `tool_call_count` | INTEGER | 工具调用次数 |
| `error_code` | VARCHAR(64) NULL | 失败时业务码 |
| `error_message` | TEXT NULL | 失败时摘要 |
| `meta` | JSONB | 扩展：`media_count`、`subagent_ids`、`flow_id`、`compliance_flags` 等 |
| `steps_summary` | JSONB NULL | 轻量步骤摘要 `[{ type, label, duration_ms }]`，非完整 steps |
| `created_at` | TIMESTAMPTZ | 调用时间 |

**索引建议：**

- `(tenant_id, agent_id, created_at DESC)` — 列表主查
- `(tenant_id, agent_id, conversation_id)` — 按会话过滤
- `(tenant_id, trace_id)` — 关联排障

### 2.2 写入时机

在 `AgentChatMixin.chat` 外层统一写入（成功与异常分支均覆盖），与 `_finish_chat_turn`、合规 `check_input` / `check_output` 同级：

```text
chat 入口 → 记录 start_time、route（路由确定后）
         → 执行各分支（A2A / 子 Agent / Flow / RAG / …）
         → 成功：写 success + previews + tokens + step_count
         → 失败 / 合规拦截：写 failed / blocked
         → 与 chat 同事务 commit（或异步 Celery 写日志表，二选一实现时定）
```

**不是**在每个 Flow 节点、RAG 节点、子 Agent 内各自写表；节点信息仅进入 `steps_summary` 或沿用现有 `ChatResponse.steps`（Trace 用）。

### 2.3 关联修正：`ModelUsageLog`

现有 `agt_model_usage_logs` 写 `source=chat` 时未带 `source_id`。P1 起写入时设置 `source_id = agent_id`，便于与调用记录对账。

### 2.4 已有表复用（只读关联，不替代主表）

| 表 | 用途 |
|----|------|
| `tool_invocation_logs` | 详情页关联工具调用（`agent_id` + 时间窗） |
| `agt_model_usage_logs` | Token 对账 |
| Hook 执行日志 | 通过 `trace_id` 跳转（P3） |

---

## 3. API

前缀：`/api/v1/agents/{agent_id}/call-records`  
权限：`agent:read`（列表 / 详情）

### 3.1 列表

```
GET /agents/{agent_id}/call-records
  ?page=1&size=20
  &status=success|failed|blocked
  &conversation_id=...
  &actor_user_id=...
  &from=2026-05-01&to=2026-05-29
  &q=关键词
  &route=subagent|flow|...
→ PageResult<AgentCallRecordOut>
```

`AgentCallRecordOut` 列表项含 `actor_username`（批量关联 `sys_users`，与审计日志一致）。

### 3.2 详情

```
GET /agents/{agent_id}/call-records/{call_id}
→ AgentCallRecordDetailOut（含 steps_summary、meta；可选 related_tool_logs）
```

### 3.3 统计 API 共用事实表

`GET /agents/{id}/stats?days=7` 从 `agt_agent_chat_calls` 聚合，替换当前全 0 占位：

| 指标 | 聚合方式 |
|------|----------|
| `sessions_total` | `COUNT(DISTINCT conversation_id)` |
| `messages_total` | `COUNT(*)` |
| `active_users_total` | `COUNT(DISTINCT actor_user_id)` |
| `avg_rounds_total` | 每会话平均轮次 |
| `*_by_day` | 按 `created_at` 日期分组 |

---

## 4. 前端

### 4.1 入口

- 对话工作台右侧栏 Tab：`调用记录`（`AGENT_WORKBENCH_TABS.call_records`，当前 `ready: false`）
- 全屏遮罩 `AgentWorkbenchOverlay`，副标题：「智能体对话调用流水」

### 4.2 UI 形态

- **表格 + 筛选条**（与审计日志、工具调用日志一致，非卡片流）
- 列：时间、状态、路径、用户、问题摘要、耗时、Token、`trace_id`
- 行点击 → **详情弹窗**（可选 URL `?call={id}`，与模型详情弹窗模式一致）
- **无 CSV 导出按钮**

### 4.3 详情弹窗

1. 概览：状态、route、耗时、Token、操作者、会话 ID  
2. 输入 / 输出 preview  
3. 步骤摘要 timeline（只读，可复用 `AgentExecutionTimeline` 思路）  
4. 操作：复制 `trace_id`；若本地存在同 `conversation_id` 会话 → 「在 Trace 中打开」

### 4.4 文件清单（待建）

```text
backend/app/models/agent_chat_call.py
backend/app/tenant/agents/schemas/call_records.py
backend/app/tenant/agents/services/call_records.py
backend/app/tenant/agents/views/call_records.py   # 或并入 agents.py

ui/workbench/features/agents/components/AgentCallRecordsPanel.tsx
ui/workbench/features/agents/components/AgentCallRecordDetailDialog.tsx
ui/workbench/features/agents/hooks/use-agent-call-records.ts
ui/workbench/lib/api/agents.ts                    # listCallRecords / getCallRecord
```

---

## 5. 与 Trace Tab 联动

| 场景 | 行为 |
|------|------|
| 本地有同 `conversation_id` 会话 | 详情 → 「在 Trace 中打开」→ 切 Tab 并 `onTraceTurnIndexChange` 定位 |
| 本地无该会话 | 提示「会话未同步到本机，仅可查看服务端摘要」 |

Trace 仍只读本地 `chat-sessions`；调用记录不替代 Trace 的完整 `steps` JSON 调试体验。

---

## 6. 测试计划

1. HTTP / WS 各发一轮对话 → 产生 1 条 `success` 记录，字段与 `ChatResponse` 一致  
2. 合规拦截 → `status=blocked`  
3. 编排异常 → `status=failed`，含 `error_message`  
4. 列表分页、按 `conversation_id` / 状态 / 时间筛选  
5. `GET /stats` 聚合与手动计数一致  
6. 子 Agent / Flow 路径 → `route` 字段正确  
7. 定时任务触发 chat → 写入记录（`actor_user_id` 为创建人或系统上下文）

---

## 7. 参考

- [platform-agents.md](./platform-agents.md) — 对话路由与 API 总览  
- [agent-chat-websocket.md](./agent-chat-websocket.md) — WS 与 HTTP 双通道  
- [realtime-transport-design.md](../architecture/realtime-transport-design.md) — 会话持久化 v2 路线图  

---

## 8. 可观测性：业务记录 vs OpenTelemetry

### 8.1 当前选择

| 层级 | 方案 | 说明 |
|------|------|------|
| **产品 / 租户** | `agt_agent_chat_calls` | 业务审计、工作台查询、统计口径 |
| **请求关联** | 现有 HTTP `trace_id` 中间件 | 单次请求 ID，写入调用记录便于排障 |
| **基础设施追踪** | OpenTelemetry | **v1 不接入**；后续 SRE 需要时再立项 |

### 8.2 与 OpenTelemetry 的区别

| 维度 | 调用记录（本文） | OpenTelemetry |
|------|------------------|---------------|
| 目的 | 租户侧业务审计 / 运维查账 | 系统可观测性（性能、依赖、故障） |
| 数据形态 | PG 领域表，字段带业务语义 | Trace（Span 树）+ Metrics + Logs |
| 粒度 | 一轮对话 ≈ 1 行 | HTTP、DB、LLM、RPC 各可为 Span |
| 写入 | chat 收尾显式写 PG | SDK 自动埋点 + `traceparent` 传播 |
| 查询 | 工作台按 agent 分页、RBAC | Jaeger / Tempo / Datadog 等 |
| 保留 | 按租户与合规设计 | 通常短保留、技术视角 |

### 8.3 后续接入 OpenTelemetry 时的关系（非 v1）

```text
OpenTelemetry Span 树  ←→  HTTP trace_id  ←→  agt_agent_chat_calls.trace_id
```

- OTel **不替代**业务表；工作台「调用记录」仍查 PG。  
- OTel 负责火焰图、延迟分解、跨服务传播；业务表负责「谁调了哪个 agent、成败、Token、合规状态」。  
- 接入时优先：HTTP / LLM / 工具调用 Span；`trace_id` 与 OTel Trace ID 对齐或映射。

---

## 9. 变更记录

| 日期 | 说明 |
|------|------|
| 2026-05-29 | P2：agt_chat_sessions/messages、chat 自动持久化、会话 API、本地合并与调用记录 Trace 回放 |
| 2026-05-29 | P3：blocked 快捷筛选；详情关联 tool/hook 日志；hook trace_id 索引 |
| 2026-05-29 | P1：stats 从 call-records 聚合；ModelUsageLog source_id=agent_id；调用记录写入 Token |
| 2026-05-29 | P0：agt_agent_chat_calls 表、chat 写入、列表/详情 API、工作台表格与详情弹窗 |
| 2026-05-29 | 初版：业务调用记录设计；明确 v1 不做 CSV 导出、不接入 OpenTelemetry |
