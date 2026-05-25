# MCP 服务技术方案

Model Context Protocol（MCP）在 MilesAI 中用于**注册远程工具服务**、**同步 `tools/list`**、**试调用 `tools/call`**，并通过智能体 `config.mcp_service_ids` 将工具说明注入对话上下文。

## 1. 能力范围

| 阶段 | HTTP | SSE | STDIO |
|------|------|-----|-------|
| Phase 1 | 注册 / 同步 / 列表 UI | 同左 | 仅入库，不同步 |
| **Phase 2** | **真 invoke** + Streamable HTTP（JSON 或 SSE 响应） | **长连接 Legacy SSE** + 回退 | 不支持 invoke |
| 规划 | 会话复用 / DELETE 终止 | GET 通知流 | 依赖[沙箱方案](../architecture/mcp-sandbox.md) |

说明：

- **HTTP**：优先 [Streamable HTTP](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports#streamable-http)（`Accept: application/json, text/event-stream`），POST 响应可为 JSON 或 SSE；失败则回退单 POST JSON。
- **SSE（transport=sse）**：优先 **Legacy HTTP+SSE**（2024-11-05）：`GET endpoint_url` 收 `event: endpoint` → 向返回的 message URL `POST` JSON-RPC → 在 `event: message` 中收响应；可选 `initialize` + `notifications/initialized`。若未收到 endpoint 事件，自动回退 Streamable HTTP / 简单 POST。
- **STDIO** 见 [mcp-sandbox.md](../architecture/mcp-sandbox.md)。

## 2. 数据模型

表：`tool_mcp_services`（`app/tenant/mcp/models.py`）

| 字段 | 说明 |
|------|------|
| `name` | 租户内唯一显示名 |
| `endpoint_url` | HTTP(S) 端点；STDIO 为 `stdio://{name}` 占位 |
| `transport` | `http` \| `sse` \| `stdio`（`streamable-http` 归一为 `http`） |
| `description` | 卡片副标题 |
| `connection_config` | JSON：见下表 |
| `tools_cache` | 最近一次 `tools/list` 结果 |
| `last_sync_at` / `sync_error` / `status` | 同步状态 |

**`connection_config` 常用键**

| 键 | 类型 | 说明 |
|----|------|------|
| `endpoint_url` | string | 与列字段冗余，便于 PATCH 只改配置 |
| `headers` | object | 出站请求附加头（如 `Authorization`） |
| `timeout_sec` | number | 单次 RPC 超时，上限 120s |
| `mcp_initialize` | boolean | Legacy SSE 是否先发 `initialize`（默认 `true`） |
| `session_id` | string | Streamable HTTP 的 `Mcp-Session-Id`（可选，跨请求复用） |
| `command` / `args` / `env` | — | 仅 STDIO 创建时使用 |

## 3. API

前缀：`/api/v1/mcp`（租户 JWT + `mcp:read` / `mcp:write`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/mcp?transport=&page=&size=` | 列表；`transport` 可选 `http` \| `sse` \| `stdio` |
| POST | `/mcp` | 创建 |
| PATCH | `/mcp/{id}` | 编辑 |
| DELETE | `/mcp/{id}` | 软删 |
| POST | `/mcp/{id}/sync` | `tools/list` 写入 `tools_cache` |
| POST | `/mcp/{id}/tools/{tool_name}/invoke` | **`tools/call`（Phase 2 真远程调用）** |

### invoke 请求 / 响应

```json
// POST .../invoke
{ "params": { "key": "value" } }

// 200 output 示例
{
  "content": [{ "type": "text", "text": "..." }],
  "text": "聚合后的文本",
  "isError": false,
  "structuredContent": null
}
```

远程 JSON-RPC 错误 → HTTP 400，`message` 含 MCP 错误信息。

## 4. 传输与调用链

### 4.1 Legacy SSE（`transport=sse`）

```text
Client                          MCP Server
  |-- GET /sse (Accept: text/event-stream) -->|
  |<-- event: endpoint  data: /messages?... --|
  |-- POST /messages  initialize ----------->|
  |<-- event: message   {id, result} --------|
  |-- POST /messages  notifications/initialized ->|
  |-- POST /messages  tools/list ----------->|
  |<-- event: message   {id, result} --------|
```

- `endpoint_url` 应填 **SSE GET 入口**（如 `http://host:3001/sse`），不是 message POST 地址。
- POST URL 必须与 GET **同源**（防 endpoint 事件 SSRF）。

### 4.2 Streamable HTTP（`transport=http` 或 SSE 回退）

```text
POST /mcp  (Accept: application/json, text/event-stream)
  → Content-Type: application/json  → 直接解析 JSON-RPC
  → Content-Type: text/event-stream → 读 event:message 直至匹配 id
```

### 4.3 应用内链路

```
POST /mcp/{id}/sync | .../invoke
  → McpServiceManager
  → client.mcp_json_rpc (按 transport 分支)
  → sse_transport.legacy_sse_json_rpc | streamable_http_json_rpc | 简单 POST
  → rpc.parse_jsonrpc_result / normalize_tool_call_result
```

## 5. 代码结构

| 模块 | 路径 | 说明 |
|------|------|------|
| 包说明 | `app/tenant/mcp/__init__.py` | 分层与 Phase |
| 模型 | `app/tenant/mcp/models.py` | `tool_mcp_services` |
| JSON-RPC 客户端 | `app/tenant/mcp/client.py` | **降级链入口** `mcp_json_rpc` |
| Legacy / Streamable SSE | `app/tenant/mcp/sse_transport.py` | 长连接与 Streamable POST |
| JSON-RPC 解析 | `app/tenant/mcp/rpc.py` | `parse_jsonrpc_result` |
| 连接安全 | `app/tenant/mcp/security.py` | SSRF、`MCP_ALLOW_PRIVATE_HOSTS` |
| 业务 | `app/tenant/mcp/services/mcp.py` | sync / invoke 落库 |
| 路由 | `app/tenant/mcp/views/mcp.py` | REST API |
| 传输归一化 | `app/tenant/mcp/transport.py` | http / sse / stdio |
| 前端 | `frontend/app/workbench/mcp/`，`frontend/components/mcp/` | Tab 与卡片 |

## 6. 与智能体 / 工具目录集成

- **智能体**：`config.mcp_service_ids` → `build_skill_mcp_prompt_block` 注入已同步工具名称与描述。
- **工具目录**：`GET /tools/catalog` 合并各 MCP 的 `tools_cache`（`source=mcp`）。
- **对话内自动调工具**：当前为提示词注入；LangChain/DeepAgents 将 MCP 注册为可执行 Tool 为后续迭代。

## 7. 连接安全（Phase 2，非沙箱）

配置项：`MCP_ALLOW_PRIVATE_HOSTS`（默认 `true`，开发可连 `127.0.0.1`）。

为 `false` 时：

- 拒绝 `localhost`、`127.0.0.1` 及 RFC1918 等内网 IP
- 仅允许 `http` / `https` scheme
- HTTP 客户端 `follow_redirects=false`，降低开放重定向 SSRF

生产部署建议在 `.env` 中设置：

```bash
MCP_ALLOW_PRIVATE_HOSTS=false
```

更完整的进程隔离与命令执行约束见 [mcp-sandbox.md](../architecture/mcp-sandbox.md)。

## 8. 运维与排错

| 现象 | 处理 |
|------|------|
| 同步 0 工具 | 确认对端支持 `tools/list`；SSE 是否填 `/sse` 而非 `/messages` |
| SSE 未收到 endpoint | URL 应为 GET SSE 入口；或改用 HTTP transport |
| invoke 400 连接失败 | 网络、TLS、防火墙、`MCP_ALLOW_PRIVATE_HOSTS` |
| invoke 400 MCP 远程错误 | 对端 `error.message`；参数是否符合 tool schema |
| STDIO 同步失败 | 预期行为；待沙箱 + Phase 3 |

## 9. 迁移

```bash
cd backend && alembic upgrade head   # 含 004_mcp_fields
```

## 10. 相关文档

- [MCP 沙箱方案（STDIO / 平台执行）](../architecture/mcp-sandbox.md)
- [技术设计总览 §11.3](../architecture/technical-design.md)
- [AI 栈与工具](../guides/ai-stack.md)
- [流程画布与 compiler](../guides/flows.md)（与 MCP 独立；画布 `KnowledgeSearch` 走 KB RAG）
