# 智能体 API 对接调试

**日期：** 2026-07-15  
**状态：** 一期已实现  
**PRD 对照：** 模块4 智能体管理（工作台 API Tab）  
**设计：** [2026-07-15-agent-api-access-design.md](../superpowers/specs/2026-07-15-agent-api-access-design.md)

---

## 1. 背景与目标

工作台右侧「API」Tab 提供 HTTP 对话对接说明，并签发短期调试 Token，便于用 curl / 脚本试通 `POST …/chat`，无需抄浏览器登录态。

## 2. 一期交付

| 项 | 说明 |
|----|------|
| UI | `AgentApiPanel`：Endpoint、鉴权、请求/响应、curl / Python、生成调试 Token |
| 接口 | `POST /api/v1/agents/{agent_id}/api-access/debug-token` |
| 对话 | 复用 `POST /api/v1/agents/{agent_id}/chat` |

## 3. API

### 3.1 签发调试 Token

```http
POST /api/v1/agents/{agent_id}/api-access/debug-token
Authorization: Bearer <工作台登录 JWT>
Permission: agent:write
```

响应 `data`：`access_token`、`token_type`（bearer）、`expires_in`、`expires_at`、`agent_id`、`purpose`（`agent_api_debug`）、`warning`。

TTL：配置 `agent_api_debug_token_ttl_hours`（默认 24）。JWT claim 含 `purpose`、`agent_id`（一期仅审计，不收窄路由权限）。签发后登记 Redis 会话（`user-agent` 含 `agent-api-debug`）。

### 3.2 对话（复用）

```http
POST /api/v1/agents/{agent_id}/chat
Authorization: Bearer <debug_token>
Permission: agent:read
```

## 4. UI 入口

`/workbench/agents/chat?agent={id}&tab=api`

## 5. 明确不做（二期）

- 智能体 API Key 表与吊销列表  
- 独立对外路由（如 `/open/agents/...`）  
- WebSocket / 会话 / 调用记录对接文档  
- 页内直接发起真实 chat  

## 6. 相关文档

- [platform-agents.md](./platform-agents.md)  
- [agent-chat-websocket.md](./agent-chat-websocket.md)（WS 仍仅工作台）  
