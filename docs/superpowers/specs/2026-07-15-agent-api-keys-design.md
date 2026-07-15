# 智能体正式 API Key 与开放调用（二期）

**日期：** 2026-07-15  
**状态：** 已实现  
**范围：** 工作台 API Tab 密钥管理 + `X-API-Key` 调用对话  
**依赖一期：** [2026-07-15-agent-api-access-design.md](./2026-07-15-agent-api-access-design.md)（调试 Token 与对接文档页）  
**选定方案：** Key 身份映射创建者用户 + 专用鉴权依赖；双路径调用

## 背景与目标

一期提供短期调试 JWT（等效登录态）。二期提供**按智能体绑定的正式 API Key**，供生产脚本/系统对接：不过期、可吊销；对外主推独立 open 入口。

**已确认决策：**

| 项 | 选择 |
|----|------|
| 范围 | Key 管理 + 挂现有 chat + 独立 open 入口（A+B） |
| Header | 专用 `X-API-Key` |
| 路由 | `/agents/{id}/chat`：JWT **或** Key；`/open/agents/{id}/chat`：**仅** Key |
| 生命周期 | 不过期，手动吊销 |
| 身份 | 映射 Key `created_by` 用户（方案 1） |

**成功标准：**

1. 创建 Key → 复制明文 → `X-API-Key` 调 open chat 成功  
2. 吊销后同 Key → 401  
3. Key 调其它智能体 id → 403  
4. open 不带 Key（仅 JWT）→ 401  

## 明确不做

- Key 过期时间、限流配额 UI、IP 白名单  
- WebSocket / SDK  
- 租户级全局 Key（仅按智能体）  
- 无 `user_id` 的纯服务身份 Context（方案 2）  

## 数据模型

### 表 `agt_agent_api_keys`

| 列 | 类型 | 说明 |
|----|------|------|
| `id` | UUID PK | |
| `tenant_id` | UUID | 租户隔离 |
| `agent_id` | UUID | 绑定智能体 |
| `name` | string(64) | 展示名 |
| `key_prefix` | string(16) | 列表展示 / 识别 |
| `key_hash` | string | 明文哈希，不可逆 |
| `created_by` | UUID | 创建者 user_id |
| `last_used_at` | timestamptz NULL | 鉴权成功更新 |
| `revoked_at` | timestamptz NULL | 非空即吊销 |
| `created_at` / `updated_at` | timestamptz | TimestampMixin |

- 索引：`(tenant_id, agent_id)`；`key_hash` 唯一（或 prefix+hash）  
- 软删：仅用 `revoked_at`，不用双重 `deleted_at`  
- 每智能体最多 **8** 个 Key（含已吊销是否占名额：建议**仅 active 计数**，吊销后可再建）

### 明文格式

```text
mil_<prefix8>_<secret32>
```

- 完整串仅创建响应返回一次  
- `key_hash`：`sha256(明文)` 或带全局 pepper 的 HMAC（与项目既有密钥习惯对齐，实现时择一写死）  
- 列表字段：`id`、`name`、`key_prefix`、`created_at`、`last_used_at`、`status`（active|revoked），**无 secret**

### 调用记录

`agt_agent_chat_calls` 新增可空列 `source`（varchar 16）：

- `workbench` — 工作台登录 JWT  
- `debug_token` — `purpose=agent_api_debug`  
- `api_key` — `X-API-Key`  

Key 路径：`actor_user_id = created_by`。

## 鉴权流

```text
有 X-API-Key？
  → hash 查库 → 吊销/缺失 401
  → agent_id ≠ 路径 id → 403
  → 加载 created_by（禁用则 401）
  → TenantContext(创建者, 具备 agent:read 语义, auth_via=api_key)
  → 更新 last_used_at
无 X-API-Key？
  → open → 401
  → /agents/.../chat → 现有 Bearer JWT / 调试 Token
```

`X-API-Key` 与 `Authorization` 同时出现时：**优先 `X-API-Key`**。

Key 调用路径不再按创建者完整菜单 RBAC 细验，固定等价「可对该 agent chat」；创建/吊销仍需工作台 JWT + `agent:write`。

### TenantContext

可选扩展 `auth_via: "jwt" | "api_key" | "debug_token" | None`，供写 `source`。

## 路由

| 方法路径 | 鉴权 | 说明 |
|----------|------|------|
| `GET /agents/{id}/api-access/keys` | JWT `agent:write` | 列表；`?include_revoked=1` 可选 |
| `POST /agents/{id}/api-access/keys` | JWT `agent:write` | body `{ name }`；响应含一次性 `secret` |
| `POST /agents/{id}/api-access/keys/{key_id}/revoke` | JWT `agent:write` | 幂等吊销 |
| `POST /agents/{id}/chat` | JWT **或** Key | 现有 chat，换 Depends |
| `POST /open/agents/{id}/chat` | **仅** Key | 复用 `AgentService.chat`；OpenAPI tag「开放调用」 |
| `POST /agents/{id}/api-access/debug-token` | 一期不变 | 调试用 |

open 挂在 `/api/v1/open/...`，请求/响应与 `ChatRequest` / `ChatResponse` / `ApiResponse` 一致。

## UI

`AgentApiPanel`：

1. **密钥管理**：创建（名称）+ 表格（prefix、状态、时间、吊销）  
2. **创建成功弹层**：完整 secret 仅此一次可复制  
3. **对接文档主推** open URL + `X-API-Key`  
4. **调试 Token** 折叠降级为「快速试通，勿用于生产」  

## 安全

- 明文不落库、不进应用日志  
- 吊销立即生效；不可改绑 agent  
- open 不做 Cookie/CSRF 假设  

## 测试计划

1. 创建 Key → secret 仅创建响应；列表无 secret  
2. Key → open chat 200（可 mock LLM）  
3. Key → `/agents/{id}/chat` 200  
4. 吊销后 401  
5. 跨 agent 403  
6. open 仅 JWT → 401  
7. active 数 >8 → 400  
8. 调用记录 `source=api_key`  

## 文件清单（预期）

| 区域 | 路径 |
|------|------|
| 迁移 | `agt_agent_api_keys`；`agt_agent_chat_calls.source` |
| Model / schema / service | `tenant/agents` 下 api_access 扩展 |
| deps | `require_agent_api_key`、`require_agent_chat_auth` |
| open router | `tenant/.../open` 或 agents 子路由 |
| UI / api client / types | workbench `features/agents` |
| 文档 | 更新 `docs/features/agent-api-access.md` |

## 与一期关系

- 调试 Token 保留；文档与 UI 标明非生产  
- 正式集成以 open + API Key 为准  
