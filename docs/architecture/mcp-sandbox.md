# MCP 沙箱与执行隔离方案

**状态：** 目标架构（mcp-runner 已部分落地；STDIO 沙箱 MVP 进行中）  
**As-Is 规格：** [features/tools-mcp-skills.md](../features/tools-mcp-skills.md) · **实现指南：** [guides/mcp.md](../guides/mcp.md)

本文描述 **STDIO 传输**、**平台内执行用户命令**、以及 **高敏感工具调用** 所需的隔离边界。  
**HTTP/SSE 远程 invoke（Phase 2）不经过本沙箱**，仅受 [连接安全](../guides/mcp.md#7-连接安全phase-2非沙箱) 约束。

## 1. 为什么要沙箱

| 场景 | 风险 | 是否需要沙箱 |
|------|------|----------------|
| HTTP/SSE 调用**外部** MCP URL | SSRF、数据外传 | 连接策略即可（已实现 `security.py`） |
| **STDIO**：`npx @vendor/mcp-server` | 任意代码、读文件、出站网络 | **必须** |
| 未来：平台托管 MCP 进程 | 多租户抢占、资源耗尽 | **必须** |
| Agent 循环调用 MCP 工具 | 滥用配额、无限调用 | 配额 + 审计（可与沙箱并列） |

结论：**Phase 2 不做沙箱也能上线 HTTP/SSE invoke**；**STDIO 或平台代跑进程前必须先落地沙箱 MVP**。

## 2. 目标与非目标

**目标（MVP）**

- 子进程与 API 进程隔离（独立 worker / 容器）
- 可配置 CPU、内存、 wall-clock 超时
- 命令白名单或「模板 + 参数」注册，禁止自由 `shell -c`
- 默认禁止或严格限制出站网络
- 审计：租户、用户、服务 ID、命令摘要、退出码

**非目标（首版不做）**

- 完整 gVisor / Firecracker 级 VM 隔离
- 用户上传任意 Docker 镜像
- 跨租户共享 MCP 进程池的热启动编排

## 3. 架构示意

```text
┌─────────────────┐     POST /mcp/{id}/sync (stdio)     ┌──────────────────────┐
│  API / Worker   │ ──────────────────────────────────► │  MCP Runner Service  │
│  (无子进程)      │         仅下发「已审批 RunSpec」        │  (低权限用户/容器)   │
└─────────────────┘                                     └──────────┬───────────┘
        │ HTTP/SSE invoke 直连远程 URL                              │ stdio 管道
        ▼                                                         ▼
┌─────────────────┐                                     ┌──────────────────────┐
│  客户 MCP Server │                                     │  npx @scope/mcp …    │
│  (公网/内网)     │                                     │  (短生命周期进程)     │
└─────────────────┘                                     └──────────────────────┘
```

- **HTTP/SSE**：API → `httpx` → 远程 URL（不启动本地命令）。
- **STDIO**：API → Runner 下发 `RunSpec` → Runner 启动子进程 → `initialize` / `tools/list` / `tools/call` → 结果回写 → 进程销毁。

## 4. RunSpec（建议数据结构）

```json
{
  "service_id": "uuid",
  "tenant_id": "uuid",
  "command": "npx",
  "args": ["-y", "@scope/mcp-server"],
  "env": { "ALLOWED_VAR": "value" },
  "cwd": null,
  "max_runtime_sec": 30,
  "max_memory_mb": 512,
  "network_mode": "deny"
}
```

校验规则：

1. `command` 必须在平台白名单（如 `npx`、`node`、`python`）或租户预置模板 ID。
2. `args` 不得含 `;`、`|`、`$()`、重定向等 shell 元字符（**不经过 shell**，`execve` 数组形式）。
3. 租户级并发上限（同时运行的 STDIO 会话数）。

## 5. 与现有表字段的关系

| 字段 | STDIO 用法 |
|------|------------|
| `transport=stdio` | 触发 Runner 路径，禁止 API 进程内 `subprocess` |
| `connection_config.command/args/env` | 生成 RunSpec 源数据 |
| `endpoint_url=stdio://...` | 占位，不参与 HTTP 客户端 |
| `tools_cache` | 由 Runner 完成 `tools/list` 后写回 |

## 6. 分阶段落地

| 阶段 | 内容 | 状态 |
|------|------|------|
| **Phase 2** | HTTP/SSE `tools/call` + `security.py` | 已完成 |
| **Phase 3** | Runner 独立服务 + STDIO sync + invoke | **已完成** |
| **Phase 4** | 预置市场 MCP 模板、npx 域名白名单、script v2 | 规划中 |

部署与运行详见 [guides/mcp.md §8](../guides/mcp.md#8-mcp-runner-部署stdio-沙箱)。

## 7. 运行方式

### 7.1 本地开发

```text
终端 1: uvicorn app.runner.main:app --port 8090
终端 2: uvicorn app.main:app --port 8000  (MCP_RUNNER_URL=http://localhost:8090)
```

- Runner 与 API 同机，隔离弱于容器，适合日常开发。
- 本机需自行安装或通过 `npm install -g` 提供 MCP 可执行文件。

### 7.2 Docker Compose

```text
docker compose -f docker-compose.infra.yml up -d
docker compose up -d --build    # 含 milesai-api + milesai-mcp-runner
```

- `mcp-runner` 不暴露 host 端口，仅 `milesai-net` 内网访问。
- 镜像 `docker/images/mcp-runner/Dockerfile` 预装 Node 与 `@modelcontextprotocol/server-everything`。
- API 环境变量：`MCP_RUNNER_URL=http://mcp-runner:8090`。

### 7.3 生产建议

```bash
MCP_ALLOW_PRIVATE_HOSTS=false
MCP_RUNNER_ENABLED=true
MCP_RUNNER_TOKEN=<random-32-bytes>   # api 与 mcp-runner 相同
MCP_RUNNER_MAX_CONCURRENT=20
MCP_RUNNER_MAX_CONCURRENT_PER_TENANT=3
```

- Runner 不对公网映射端口；仅 API 容器可访问。
- 定期查看 `mcp_runner_sessions` 审计表。

## 8. 配置建议（生产）

```bash
# 禁止 MCP 访问本机/内网（与 guides/mcp.md 一致）
MCP_ALLOW_PRIVATE_HOSTS=false

# Runner（详见 guides/mcp.md §8）
MCP_RUNNER_ENABLED=true
MCP_RUNNER_URL=http://mcp-runner:8090
MCP_RUNNER_TOKEN=<secret>
MCP_RUNNER_MAX_CONCURRENT=20
MCP_RUNNER_MAX_CONCURRENT_PER_TENANT=3
```

## 9. 审计与合规

建议写入 `mcp_runner_sessions` 及 `tenant_audit_log`（表结构见 ORM，随 `001` 迁移创建）：

- `purpose`: `mcp_sync` \| `mcp_invoke` \| `script_exec`
- `command` / `args_digest`：不含完整 env 秘密
- `status` / `exit_code` / `duration_ms` / `error_message`

## 10. 威胁模型摘要

| 威胁 | HTTP/SSE 缓解 | STDIO 缓解 |
|------|----------------|------------|
| SSRF 打内网 | `MCP_ALLOW_PRIVATE_HOSTS=false` | Runner 无内网路由 |
| 命令注入 | 不适用 | `execve` 数组 + 白名单 |
| 资源耗尽 | 超时、`timeout_sec` | cgroup / 容器 memory limit |
| 数据泄露 | TLS、租户隔离 | 进程级文件系统只读根 |
| 供应链恶意包 | 不适用 | 模板审批 + 可选镜像固定版本 |

## 11. 代码入口

| 组件 | 路径 |
|------|------|
| Runner HTTP 服务 | `app/runner/main.py` |
| 子进程会话 | `app/runner/session.py`、`app/runner/mcp_stdio.py` |
| RunSpec 校验 | `app/tenant/mcp/runner/spec.py` |
| API 侧客户端 | `app/tenant/mcp/runner/client.py` |
| 业务接入 | `app/tenant/mcp/services/mcp.py`（stdio 分支） |
| Docker 镜像 | `docker/images/mcp-runner/Dockerfile` |
| 现有 HTTP 客户端 | `app/tenant/mcp/client.py` |
| 连接安全 | `app/tenant/mcp/security.py` |

---

**状态**：HTTP/SSE invoke（Phase 2）与 STDIO Runner 沙箱（Phase 3）均已实现。部署步骤见 [guides/mcp.md §8](../guides/mcp.md#8-mcp-runner-部署stdio-沙箱)。
