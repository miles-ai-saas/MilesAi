# 智能体 API 对接

**日期：** 2026-07-15  
**状态：** 一期调试 Token ✅ · 二期正式 API Key ✅  
**设计：** [agent-api-access](../superpowers/specs/2026-07-15-agent-api-access-design.md) · [agent-api-keys](../superpowers/specs/2026-07-15-agent-api-keys-design.md)

---

## 正式对接（推荐）

```http
POST /api/v1/open/agents/{agent_id}/chat
X-API-Key: mil_<prefix>_<secret>
Content-Type: application/json
```

工作台「API」Tab 可创建 / 列表 / 吊销密钥。明文仅创建时返回一次；不过期，靠吊销失效。每智能体最多 8 个有效密钥。

兼容：`POST /api/v1/agents/{id}/chat` 亦可使用同一 `X-API-Key`（也仍支持登录 JWT / 调试 Token）。

调用记录 `source`：`workbench` | `debug_token` | `api_key`。

## 调试 Token（一期，非生产）

```http
POST /api/v1/agents/{agent_id}/api-access/debug-token
Authorization: Bearer <工作台 JWT>
Permission: agent:write
```

返回 24h access JWT（`purpose=agent_api_debug`），用于本地 curl 试通。

## 密钥管理 API

| 方法 | 路径 | 权限 |
|------|------|------|
| GET | `/agents/{id}/api-access/keys` | `agent:write` |
| POST | `/agents/{id}/api-access/keys` | `agent:write` |
| POST | `/agents/{id}/api-access/keys/{key_id}/revoke` | `agent:write` |

## UI

`/workbench/agents/chat?agent={id}&tab=api`
