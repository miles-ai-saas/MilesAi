# MCP 服务技术方案

**功能规格：** [features/tools-mcp-skills.md](../features/tools-mcp-skills.md) · 沙箱设计：[mcp-sandbox.md](../architecture/mcp-sandbox.md)

Model Context Protocol（MCP）在 MilesAI 中用于**注册远程工具服务**、**同步 `tools/list`**、**试调用 `tools/call`**，并可通过智能体 `config.mcp_service_ids` 绑定为可 **function calling** 自动调用的工具。

## 1. 能力范围

| 阶段 | HTTP | SSE | STDIO |
|------|------|-----|-------|
| Phase 1 | 注册 / 同步 / 列表 UI | 同左 | 仅入库，不同步 |
| **Phase 2** | **真 invoke** + Streamable HTTP（JSON 或 SSE 响应） | **长连接 Legacy SSE** + 回退 | 不支持 invoke |
| **Phase 3** | 同 Phase 2 | 同 Phase 2 | **MCP Runner 沙箱**：sync + invoke（需 `MCP_RUNNER_ENABLED`） |

说明：

- **HTTP**：优先 [Streamable HTTP](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports#streamable-http)（`Accept: application/json, text/event-stream`），POST 响应可为 JSON 或 SSE；失败则回退单 POST JSON。
- **SSE（transport=sse）**：优先 **Legacy HTTP+SSE**（2024-11-05）：`GET endpoint_url` 收 `event: endpoint` → 向返回的 message URL `POST` JSON-RPC → 在 `event: message` 中收响应；可选 `initialize` + `notifications/initialized`。若未收到 endpoint 事件，自动回退 Streamable HTTP / 简单 POST。
- **STDIO**：经独立 **mcp-runner** 服务在沙箱内 `execve` 子进程，API 不直接 subprocess。见 [沙箱方案](../architecture/mcp-sandbox.md)。

## 2. 数据模型

表：`tool_mcp_services`（`backend/packages/miles-portal/src/miles_portal/tenant/mcp/models.py`）

| 字段 | 说明 |
|------|------|
| `name` | 租户内唯一显示名 |
| `endpoint_url` | HTTP(S) 端点；STDIO 为 `stdio://{name}` 占位 |
| `transport` | `http` \| `sse` \| `stdio` \| `custom` |
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

## 3. 种子数据（开发演示）

```bash
cd backend
milesai seed mcp          # 仅 MCP
milesai init-db           # 含 seed all
```

每个租户幂等写入 **8 条**示例（按 `name` 去重，重复执行会更新配置）：

| 名称 | transport | status | 场景说明 |
|------|-----------|--------|----------|
| MCP示例·HTTP Streamable | http | active | 预置 fetch 类工具；端点 `127.0.0.1:3001/mcp` |
| MCP示例·SSE Legacy | sse | active | 预置 filesystem 工具；端点 `/sse` |
| MCP示例·带鉴权 HTTP | http | inactive | `headers.Authorization` 模板 |
| MCP示例·STDIO 文件系统 | stdio | inactive | `npx @modelcontextprotocol/server-filesystem` |
| MCP示例·STDIO 记忆图谱 | stdio | inactive | `npx @modelcontextprotocol/server-memory` |
| MCP示例·同步失败 | http | error | 不可达端口 + `sync_error` 文案 |
| MCP示例·待同步 | sse | inactive | 空 `tools_cache`，测首次同步 |
| MCP示例·知识检索 | http | active | 检索类工具名，便于绑智能体 |

实现：`scripts/seed/mcp.py`。`connection_config.seed_scenario` 标识场景；真实 `tools/call` 仍需可达端点或 STDIO Runner。

## 4. API

前缀：`/api/v1/mcp`（租户 JWT + `mcp:read` / `mcp:write`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/mcp?transport=&page=&size=` | 列表；`transport` 可选 `http` \| `sse` \| `stdio` |
| POST | `/mcp` | 创建 |
| PATCH | `/mcp/{id}` | 编辑 |
| DELETE | `/mcp/{id}` | 软删 |
| POST | `/mcp/{id}/sync` | `tools/list` 写入 `tools_cache` |
| POST | `/mcp/{id}/tools/{tool_name}/invoke` | **`tools/call`（真远程调用）** |

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
| 包说明 | `backend/packages/miles-portal/src/miles_portal/tenant/mcp/__init__.py` | 分层 |
| 模型 | `backend/packages/miles-portal/src/miles_portal/tenant/mcp/models.py` | `tool_mcp_services` |
| JSON-RPC 客户端 | `backend/packages/miles-portal/src/miles_portal/tenant/mcp/client.py` | **降级链入口** `mcp_json_rpc` |
| Legacy / Streamable SSE | `backend/packages/miles-portal/src/miles_portal/tenant/mcp/sse_transport.py` | 长连接与 Streamable POST |
| JSON-RPC 解析 | `backend/packages/miles-exec/src/miles_exec/mcp/rpc.py` | `parse_jsonrpc_result` |
| 连接安全 | `backend/packages/miles-portal/src/miles_portal/tenant/mcp/security.py` | SSRF、`MCP_ALLOW_PRIVATE_HOSTS` |
| 业务 | `backend/packages/miles-portal/src/miles_portal/tenant/mcp/services/mcp.py` | sync / invoke 落库 |
| 路由 | `backend/packages/miles-portal/src/miles_portal/tenant/mcp/views/mcp.py` | REST API |
| 传输归一化 | `backend/packages/miles-portal/src/miles_portal/tenant/mcp/transport.py` | http / sse / stdio |
| **Runner 客户端** | `backend/packages/miles-portal/src/miles_portal/tenant/mcp/runner/client.py` | API → Runner HTTP |
| **RunSpec** | `backend/packages/miles-exec/src/miles_exec/mcp/spec.py` | 命令校验与构建 |
| **Runner 服务** | `backend/packages/miles-runner/src/miles_runner/main.py` | 独立 uvicorn 入口 |
| 前端 | `ui/workbench/app/workbench/mcp/`，`ui/workbench/components/mcp/` | Tab 与卡片 |

## 6. 与智能体集成

- **平台工具**：`config.enable_tool_calling` + 可选 `config.tool_slugs` → `tool_agent` function calling（无 KB 时）。详见 [tools.md](./tools.md)。
- **MCP**：`config.mcp_service_ids` 绑定的服务，其 `tools_cache` 展开为 function name `mcp__{service}__{tool}`，与内置/自定义工具一同进入 `tool_agent`；执行走 `McpServiceManager.invoke_tool`，写入 `tool_invocation_logs`（`source=mcp`）。只读工具（`annotations.readOnlyHint`）免确认，其余默认需用户确认。
- **二者分离**：工具目录 `GET /tools/catalog` **不含** MCP；MCP 见 `GET /mcp`。`tool_slugs` 白名单不作用于 MCP（绑定服务即启用）。

## 7. 连接安全（非沙箱）

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

## 8. MCP Runner 部署（STDIO 沙箱）

STDIO 的 sync / invoke 依赖独立 **mcp-runner** 进程。API **不会**在本机 `subprocess` 用户命令，只通过 HTTP 调用 Runner。

### 8.1 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MCP_RUNNER_ENABLED` | `false` | API 是否允许 STDIO sync/invoke |
| `MCP_RUNNER_URL` | `http://localhost:8090` | Runner 地址；Docker 内为 `http://mcp-runner:8090` |
| `MCP_RUNNER_TOKEN` | 空 | API 与 Runner 共享密钥（请求头 `X-Runner-Token`） |
| `MCP_RUNNER_MAX_CONCURRENT_PER_TENANT` | `3` | 租户并发 STDIO 会话上限 |
| `MCP_RUNNER_MAX_CONCURRENT` | `20` | Runner 全局并发上限（仅 Runner 进程读取） |
| `MCP_RUNNER_COMMAND_WHITELIST` | `npx,node,python,python3` | 允许的 command |

生产务必设置足够长的随机 `MCP_RUNNER_TOKEN`，且 Runner **不要**映射到公网端口。

### 8.2 方式一：本地开发（推荐日常调试）

适用：本机已跑 PostgreSQL / Redis，API 用 `uvicorn --reload` 热更新。

**步骤 1 — 数据库迁移**

```bash
cd backend && alembic upgrade head   # 唯一迁移 001，按 ORM 建表
```

**步骤 2 — 启动 Runner（终端 1）**

```bash
cd backend
export MCP_RUNNER_TOKEN=dev-runner-token   # 与 API 侧保持一致
uvicorn miles_runner.main:app --host 0.0.0.0 --port 8090 --reload
```

验证：

```bash
curl http://localhost:8090/health
# {"status":"ok"}
```

**步骤 3 — 配置 API（`backend/.env` 或项目根 `.env`）**

```bash
MCP_RUNNER_ENABLED=true
MCP_RUNNER_URL=http://localhost:8090
MCP_RUNNER_TOKEN=dev-runner-token
```

**步骤 4 — 启动 API（终端 2）**

```bash
cd backend
uvicorn miles_server.main:app --host 0.0.0.0 --port 8000 --reload
```

**步骤 5 — 准备 STDIO MCP 命令**

本地若未全局安装 MCP server，可先安装测试包：

```bash
npm install -g @modelcontextprotocol/server-everything
```

在工作台 **MCP → STDIO** 创建服务，例如：

| 字段 | 示例 |
|------|------|
| command | `mcp-server-everything` |
| args | 留空 |

点击 **同步** 应写入 `tools_cache`；**试调用** 走同一 Runner。

> **npx 在线拉包**：默认 `network_mode=deny`，本地 `npx -y @scope/pkg` 会失败。可在 `connection_config` 中加 `"network_mode": "allow"`，或改用已安装的命令 / Docker 镜像预装包。

### 8.3 方式二：Docker Compose（整栈联调）

适用：与生产接近的全容器环境；Runner 镜像已预装 `@modelcontextprotocol/server-everything`。

**步骤 1 — 启动基础设施**

```bash
docker compose -f docker-compose.infra.yml up -d
```

**步骤 2 — 启动应用栈（含 api + mcp-runner）**

```bash
docker compose up -d --build
```

`docker-compose.yml`（项目根）中相关配置：

- 服务 **`mcp-runner`**：容器内监听 `8090`，映射 host `8090`；只读根文件系统 + `tmpfs`
- 服务 **`api`**：默认 `MCP_RUNNER_ENABLED=true`，`MCP_RUNNER_URL=http://mcp-runner:8090`

**步骤 3 — 配置密钥（项目根 `.env`）**

```bash
MCP_RUNNER_TOKEN=dev-runner-token-change-me   # 生产请改为随机值
MCP_RUNNER_ENABLED=true
```

修改后重建或重启 api / mcp-runner：

```bash
cd docker && docker compose up -d --build api mcp-runner
```

**步骤 4 — 验证**

```bash
# API 健康
curl http://localhost:8000/api/v1/health

# Runner 仅在 Docker 网络内可达；从 api 容器内测：
docker exec milesai-api curl -s http://mcp-runner:8090/health
```

**Docker 内试 STDIO MCP 示例**

| 字段 | 示例 |
|------|------|
| command | `mcp-server-everything` |
| args | 留空 |

### 8.4 两种方式对比

| 项 | 本地开发 | Docker Compose |
|----|----------|----------------|
| Runner 启动 | 手动 `uvicorn miles_runner.main:app` | `mcp-runner` 容器自动起 |
| API 连 Runner | `http://localhost:8090` | `http://mcp-runner:8090` |
| 预装 MCP | 需本机 `npm install -g` | 镜像内已装 `server-everything` |
| 隔离强度 | 与 API 同机，开发够用 | 只读 FS、cap_drop、独立容器 |
| 热更新 | API / Runner 均可 `--reload` | 需 rebuild 或挂载卷 |

### 8.5 STDIO connection_config 补充

| 键 | 说明 |
|----|------|
| `command` | 必填；须在白名单内 |
| `args` | 字符串数组或换行分隔；禁止 shell 元字符 |
| `env` | 环境变量；键须 `[A-Z_][A-Z0-9_]*` |
| `timeout_sec` | 单次会话超时，1–120 |
| `network_mode` | `deny`（默认）或 `allow`（允许 npx 拉包等出站） |

## 9. 运维与排错

| 现象 | 处理 |
|------|------|
| 同步 0 工具 | 确认对端支持 `tools/list`；SSE 是否填 `/sse` 而非 `/messages` |
| SSE 未收到 endpoint | URL 应为 GET SSE 入口；或改用 HTTP transport |
| invoke 400 连接失败 | 网络、TLS、防火墙、`MCP_ALLOW_PRIVATE_HOSTS` |
| invoke 400 MCP 远程错误 | 对端 `error.message`；参数是否符合 tool schema |
| STDIO 同步失败 | 确认 `MCP_RUNNER_ENABLED=true`、Runner 可达、command 在白名单；见 [§8 部署](#8-mcp-runner-部署stdio-沙箱) |
| Runner 连接失败 | 本地查 `8090` 是否监听；Docker 查 `docker compose ps mcp-runner` 与 `MCP_RUNNER_TOKEN` 一致 |
| npx 超时 / 拉包失败 | 默认 `network_mode=deny`；改 `allow` 或换预装命令 |

## 10. 迁移

```bash
cd backend && alembic upgrade head   # 唯一迁移 001_initial_schema
```

## 11. 相关文档

- [工具指南（与 MCP 关系）](./tools.md)
- [MCP 沙箱方案（STDIO / 平台执行）](../architecture/mcp-sandbox.md)
- [技术设计总览 §11.3](../architecture/technical-design.md)
- [AI 栈与工具](../guides/ai-stack.md)
- [流程画布与 compiler](../guides/flows.md)（与 MCP 独立；画布 `KnowledgeSearch` 走 KB RAG）
