# 智能体对话 WebSocket

**状态：** v1 已实现（工作台）；直连/RAG 真 token 流式 ✅；tool 路径仍切块  
**PRD 对照：** 模块4 智能体对话  
**架构：** [realtime-transport-design.md](../architecture/realtime-transport-design.md) · [technical-design.md §10](../architecture/technical-design.md#10-智能体对话)

---

## 1. 背景与目标

对话工作台在 HTTP `POST …/chat` 之外提供 **会话级 WebSocket**，用一条连接承载：发送消息、工具确认、编排 steps、回答 delta、生成任务进度与取消。

**设计原则**（见 realtime-transport-design）：对话用 WebSocket；生成任务列表/SSE 仍保留 REST，WS 内嵌 job watcher 推送进度。

### 1.1 交付范围

- 端点：`WS /api/v1/agents/{agent_id}/chat/ws?conversation_id=`
- 帧协议：Event v1 信封（`type` + `id` + `ts` + `payload`）
- 客户端事件：`chat.send`、`tool.confirm`、`generative_job.cancel`、`ping`
- 服务端事件：`chat.delta`、`chat.step`、`tool.confirm_required`、`generative_job.*`、`chat.done`、`chat.error`
- 配置：`AGENT_CHAT_WEBSOCKET_ENABLED`（默认 true）
- 前端：`useAgentChatWs` + `AgentChatWsClient`，对话页优先 WS、HTTP 降级

### 1.2 明确不做（v1）

- 对外 OpenAPI 第三方集成的 WS（仅工作台）
- tool_agent / 工具确认 / flow / A2A 路径的真 token 流（仍走 `emit_answer_deltas` 切块兜底）
- 全站统一 WebSocket 网关

### 1.3 流式现状

| 路径 | `chat.delta` 来源 |
|------|-------------------|
| 直连 LLM（`direct_chat`） | LiteLLM `stream=True` 真 token |
| RAG 最终生成（`generate_rag_answer`、LangGraph `generate`/`fallback`） | 同上 |
| tool_agent / pending_tool / flow / A2A | 整段 answer 后 `emit_answer_deltas` 切块 |

HTTP `POST …/chat` 不传 `on_delta`，仍整包返回。合规改写后以 `chat.done.answer` 为准；前端 `applyChatResponse` 用 `res.answer` 覆盖气泡。

---

## 2. 连接与鉴权

```
wss://{host}/api/v1/agents/{agent_id}/chat/ws?conversation_id={uuid}
Header: Authorization: Bearer {jwt}
```

- Query `conversation_id` 必填（1–128 字符），与 LangGraph checkpoint 隔离一致
- 鉴权失败：`4401`；功能关闭：`4403`（`agent_chat_websocket_enabled=false`）
- 权限：`agent:read`

---

## 3. 协议

### 3.1 信封

```json
{
  "type": "chat.delta",
  "id": "uuid",
  "ts": "2026-05-27T08:00:00Z",
  "payload": { "text": "..." }
}
```

### 3.2 客户端 → 服务端

| type | payload | 说明 |
|------|---------|------|
| `chat.send` | `query`, `media[]`, `inputs`, `conversation_id`（服务端以 query 为准） | 发起一轮对话 |
| `tool.confirm` | 同 send + `pending_tool_slug` / `pending_tool_params` | 内部转为 `tool_confirmed=true` |
| `generative_job.cancel` | `job_id` | 取消进行中的生成任务 |
| `ping` | `{}` | 心跳 |

### 3.3 服务端 → 客户端

| type | 说明 |
|------|------|
| `chat.step` | 编排步骤（与 HTTP `steps` 一致） |
| `tool.confirm_required` | 待用户确认的工具 |
| `chat.delta` | 回答文本片段（直连/RAG 为 LiteLLM 真 token；tool 等路径为切块兜底） |
| `chat.done` | 完整 `ChatResponse` JSON |
| `generative_job.progress` / `generative_job.done` | job watcher 推送 |
| `chat.error` | 业务或校验错误 |
| `pong` | 心跳响应 |

---

## 4. 执行链路

```
客户端 chat.send
    → AgentService.chat(agent_id, ChatRequest, on_delta?)
    → 合规 / 钩子 / 编排（与 HTTP 相同）
    → tool.confirm_required? → 等待 tool.confirm
    → chat.step × N
    → chat.delta × N
        · 直连/RAG：LiteLLM stream → on_delta → chat.delta（真 token）
        · 其他路径：无 on_delta → emit_answer_deltas 切块
    → chat.done（含最终 answer；合规后可能与 delta 累计略有差异）
    → spawn_job_watchers(pending generative_job ids)
```

Job watcher 轮询 `generative_jobs` 状态，经 WS 推送 progress/done；客户端也可 `generative_job.cancel`。

---

## 5. 配置

| 变量 | 默认 | 说明 |
|------|------|------|
| `AGENT_CHAT_WEBSOCKET_ENABLED` | `true` | 关闭后 WS 握手 4403 |

前端：`NEXT_PUBLIC_AGENT_CHAT_WS_ENABLED`（`isAgentChatWsEnabled()`）与后端独立，便于灰度。

---

## 6. 前端

### 6.1 入口

- `/workbench/agents/chat?agent={id}` — WS 与 HTTP 双通道，WS ready 时优先 send

### 6.2 文件清单

```
ui/workbench/hooks/use-agent-chat-ws.ts
ui/workbench/lib/agent-chat-ws.ts           # URL 构建、AgentChatWsClient
ui/workbench/app/workbench/agents/chat/page.tsx
```

---

## 7. 后端文件清单

```
backend/packages/miles-portal/src/miles_portal/tenant/agents/ws/chat.py       # WebSocket 端点
backend/packages/miles-portal/src/miles_portal/tenant/agents/ws/protocol.py   # 帧类型与 envelope
backend/packages/miles-portal/src/miles_portal/tenant/agents/ws/auth.py       # JWT 解析 → TenantContext
backend/packages/miles-portal/src/miles_portal/tenant/agents/ws/job_watch.py  # 生成任务 watcher
backend/packages/miles-portal/src/miles_portal/tenant/agents/views/agents.py  # include_router(ws)
backend/packages/miles-core/src/miles_core/config.py                          # agent_chat_websocket_enabled
```

---

## 8. 测试计划

1. 带 JWT 连接 → ping/pong → chat.send → 收到 step + delta + done
2. 触发需确认工具 → `tool.confirm_required` → tool.confirm → 继续
3. 触发异步生图 → job watcher progress → done；cancel 生效
4. 无 token / 错误 token → 4401；disabled → 4403
5. HTTP 与 WS 同一 conversation_id checkpoint 行为一致

---

## 9. 参考

- [realtime-transport-design.md](../architecture/realtime-transport-design.md) — 分场景选型与 To-Be
- [attachments-media-generative.md](./attachments-media-generative.md) — 生成任务与 SSE
- [platform-agents.md](../guides/platform-agents.md) — AgentService.chat 路由
