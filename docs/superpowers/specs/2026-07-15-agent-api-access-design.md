# 智能体工作台「API」Tab：对接调试（一期）与正式 Key（二期边界）

**日期：** 2026-07-15  
**状态：** 待实现  
**范围：** 工作台右侧「API」Tab（当前 `ready: false` / 待开）  
**选定方案：** 一期 = 文档页 + 短期调试 JWT；二期 = 智能体 API Key + 独立调用入口（本文件仅定边界）

## 背景与目标

对话工作台侧栏已有配置 / Trace / 定时 / 架构 / 调用记录 / 统计，「API」仍为占位。目标是让开发者在本页完成 **HTTP 对话对接试通**，不必抄浏览器登录态。

**一期成功标准：**

1. 选中智能体 → 打开 API Tab → 生成调试 Token → curl 调 `POST …/chat` 成功  
2. Token 过期或缺失 → 401  
3. 跨租户 / 无权限行为与现有 agent API 一致  

**产品分期（已确认）：** 先文档 + 调试 Token，再正式 Key（分期 C）。  
**一期文档范围（已确认）：** 仅 HTTP `POST …/chat`（不含 WS / 会话 / 调用记录文档）。  
**一期鉴权（已确认）：** Tab 内签发短期调试 Token（默认 24h）。

## 明确不做（一期）

- 智能体级 API Key 表、吊销列表、限流配额 UI  
- 独立对外路由（如 `/open/agents/...`）  
- WebSocket / 会话 / 调用记录的对接文档  
- 真流式推送、第三方 SDK 发布  
- 页内直接发起真实 chat 试调用（验通用外部 curl / 脚本）

## 架构与数据流

```text
AgentApiPanel
  → POST /agents/{id}/api-access/debug-token   （工作台登录 JWT + agent:write）
  → 外部客户端用 debug_token
  → POST /agents/{id}/chat                     （现有路由；agent:read）
  → 调用记录 / 统计与工作台同源写入
```

### 调试 Token 形态

| 项 | 约定 |
|----|------|
| 载体 | 与登录相同的 access JWT（`type=access`，`sub=user_id`，含 `tenant_id`） |
| 额外 claim | `purpose: "agent_api_debug"`、`agent_id: "<uuid>"`（一期仅审计/展示，**不**据此收窄可访问路由） |
| TTL | 默认 24h；配置项 `agent_api_debug_token_ttl_hours`（**不**复用全局 `access_token_expire_minutes`） |
| 会话 | 签发后 `session_store.register_session`（建议 `user_agent` 含 `agent-api-debug`）；登出/黑名单 jti 后失效 |
| 吊销 | 一期无独立吊销；依赖过期或用户登出相关会话 |

**权限：**

- 签发：`agent:write`  
- 调用 chat：现有 `agent:read`  
- 文档注明：调试 Token 等效当前用户会话，可调用其它已授权租户 API；勿外泄。

**前端挂载：**

- `AGENT_WORKBENCH_TABS`：`api.ready = true`  
- `AgentWorkbenchOverlay`：`activeTab === "api"` → `AgentApiPanel`  
- `baseUrl`：`NEXT_PUBLIC_API_URL`

**路径前缀：** 一期与二期共用 `api-access`，二期再挂 `…/keys`。

## API 契约

### 签发调试 Token

```http
POST /api/v1/agents/{agent_id}/api-access/debug-token
Authorization: Bearer <工作台登录 JWT>
Permission: agent:write
```

请求体：无。

响应 `data`：

| 字段 | 类型 | 说明 |
|------|------|------|
| `access_token` | string | 调试 JWT（仅此响应返回明文） |
| `token_type` | string | `"bearer"` |
| `expires_in` | int | 秒（默认 86400） |
| `expires_at` | string | ISO8601 UTC |
| `agent_id` | UUID | 与路径一致 |
| `purpose` | string | `"agent_api_debug"` |
| `warning` | string | 固定安全提示文案 |

错误：未登录 401；无 `agent:write` 403；智能体不存在/跨租户与现有 get_agent 一致（404）。

### 对话（复用，文档展示）

```http
POST /api/v1/agents/{agent_id}/chat
Authorization: Bearer <debug_token>
Permission: agent:read
```

文档请求精简示例：

```json
{
  "query": "你好",
  "conversation_id": "可选，多轮线程后缀",
  "media": [],
  "inputs": {}
}
```

完整字段以现有 `ChatRequest` / OpenAPI 为准；进阶字段（工具确认、生图预设等）面板内用一句说明，不展开成长文档。

响应要点：`answer`、`sources`、`steps`、`artifacts`、`pending_tool`、`generative_jobs`；统一包在 `ApiResponse` 中。一期不讲 WS；异步生成注明需另途处理。

## UI：`AgentApiPanel`

自上而下：

1. **说明条** — 一期为对接调试；正式 Key 与独立入口后续提供  
2. **调用信息** — Method + 完整 URL（可复制）；Header 说明  
3. **调试 Token** — 生成 / 显隐 / 复制 / 过期时间；展示 `warning`；再次生成时提示「旧 Token 未主动吊销，仍可用至过期」  
4. **请求示例** — JSON 可复制  
5. **代码示例** — `curl` | `Python`；有 Token 则注入，否则 `YOUR_TOKEN`  
6. **响应示例** — 静态成功样例  

Client：`createAgentDebugToken(agentId)`。

## 错误与安全

| 场景 | 行为 |
|------|------|
| Token 过期 / 非 access | 401 |
| jti 黑名单 | 401 |
| `purpose` / `agent_id` claim | 一期不强制与路径 agent_id 校验 |
| 智能体 disabled | 与现有 chat 一致 |
| 重复生成 | 新旧 Token 并存至各自过期 |

安全要点：明文仅响应一次；默认 UI 遮掩；禁止把 Token 放进 query 或提交仓库；生产假定 HTTPS。

## 测试计划

1. 有 `agent:write` 签发成功，payload 含 `purpose`、`agent_id`，`expires_in`≈24h  
2. 仅 `agent:read` → 403  
3. 跨租户 agent → 404  
4. 调试 Token 调本智能体 chat → 200（可 mock LLM）  
5. 过期 Token → 401  
6. UI：Tab 无「待开」；生成后复制 curl 可联调成功  

## 文件清单（一期）

| 区域 | 路径 |
|------|------|
| Schema | `backend/app/tenant/agents/schemas/api_access.py` |
| View | `backend/app/tenant/agents/views/agents.py` |
| Service | `backend/app/tenant/agents/services/api_access.py`（或并入 agent service） |
| Config | `backend/app/core/config.py`（`agent_api_debug_token_ttl_hours`） |
| Tests | `backend/tests/tenant/agents/test_api_access.py` |
| UI | `ui/workbench/features/agents/components/AgentApiPanel.tsx`（+ 可选 hook） |
| 挂载 | `AgentWorkbenchOverlay.tsx`、`use-agents-chat-layout.ts` |
| Client / types | `ui/workbench/lib/api`、类型定义处 |
| 功能文档 | 实现时补 `docs/features/agent-api-access.md` |

## 附录：二期边界（不实现）

- 表 `agt_agent_api_keys`（哈希存储、prefix 展示、last_used、revoked_at）  
- `…/api-access/keys` CRUD；明文仅创建时一次展示  
- 独立调用入口（如 `POST /open/agents/{id}/chat`）+ Key 鉴权，权限收窄到该智能体 chat  
- 调用记录 `source` 区分 `workbench` | `debug_token` | `api_key`  
- API Tab 升级为「密钥管理 + 正式对接文档」；调试 Token 可保留为快速试通或降级  

## 决策记录

| 决策 | 选择 |
|------|------|
| 分期 | 先文档调试，后正式 Key |
| 一期文档面 | 仅 HTTP chat |
| 一期鉴权 | 短期调试 JWT（默认 24h） |
| 实现形态 | 前端文档面板 + `debug-token` 接口；对话复用现有 chat |
| 签发权限 | `agent:write` |
| claim 收窄 | 一期不做路径级强制校验 |
