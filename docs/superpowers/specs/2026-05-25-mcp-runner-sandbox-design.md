# MCP Runner 沙箱实现技术方案

> **归档：** 立项过程稿（2026-05-25）。**现网规格：** [features/tools-mcp-skills.md](../../features/tools-mcp-skills.md) · [architecture/mcp-sandbox.md](../../architecture/mcp-sandbox.md)

**日期：** 2026-05-25  
**状态：** 归档（MVP 已部分落地；以 features 为准）  
**依赖基线：** [mcp-sandbox.md](../../architecture/mcp-sandbox.md)（架构原则）、[mcp.md](../../guides/mcp.md)（Phase 2 已完成）  
**关联：** 工具 v2 `tool_type=script` 复用同一 Runner

---

## 1. 背景与目标

### 1.1 现状

| 能力 | 状态 |
|------|------|
| HTTP/SSE MCP sync + invoke | ✅ 已实现（`client.py` / `sse_transport.py`） |
| 出站 URL 安全（SSRF） | ✅ `url_security.py` + `MCP_ALLOW_PRIVATE_HOSTS` |
| STDIO MCP 入库 | ✅ 可创建，`sync`/`invoke` 拒绝 |
| 工具调用审计 | ✅ `tool_invocation_logs`（builtin/custom） |
| **进程沙箱 / Runner** | ❌ 仅设计文档，无代码 |

STDIO 当前拒绝文案：`STDIO 工具同步将在后续版本支持，请暂时使用 HTTP 或 SSE`（`mcp.py`）。

### 1.2 本期目标（Phase 3 MVP）

1. **独立 MCP Runner 服务**：API 进程永不 `subprocess` 用户命令。
2. **STDIO MCP 真 sync**：`POST /mcp/{id}/sync` 对 `transport=stdio` 走 Runner → `tools/list` → 写 `tools_cache`。
3. **STDIO MCP 真 invoke**：`POST /mcp/{id}/tools/{name}/invoke` 走 Runner → `tools/call`。
4. **RunSpec 校验与白名单**：命令、参数、资源、网络策略可配置。
5. **审计**：Runner 会话与 MCP invoke 写入审计表。
6. **Docker 可部署**：`docker-compose` 增加 `mcp-runner` 服务。

### 1.3 非目标（MVP 不做）

- gVisor / Firecracker VM 级隔离
- 用户上传任意 Docker 镜像
- STDIO 长连接会话池 / 热复用（Phase 3b）
- 在线 Python 脚本工具（工具 v2，Runner 就绪后复用）
- Agent 自动注册 MCP 为 LangChain Tool（独立迭代）

---

## 2. 总体架构

```text
                    ┌─────────────────────────────────────────┐
                    │           milesai-api / worker           │
                    │  McpServiceManager.sync_service          │
                    │  McpServiceManager.invoke_tool           │
                    │  （stdio 分支 → RunnerClient，无 subprocess）│
                    └───────────────────┬─────────────────────┘
                                        │ HTTPS + X-Runner-Token
                                        │ POST /runner/v1/sessions
                                        ▼
                    ┌─────────────────────────────────────────┐
                    │         mcp-runner（独立容器/进程）        │
                    │  ┌─────────────┐    ┌─────────────────┐ │
                    │  │ RunSpec 校验 │ → │ SessionManager  │ │
                    │  └─────────────┘    │  execve + 管道   │ │
                    │                     │  MCP stdio 协议  │ │
                    │                     └────────┬────────┘ │
                    │                              │           │
                    │                     短生命周期子进程       │
                    │                     npx/node/python …    │
                    └─────────────────────────────────────────┘
```

**关键约束：**

- API ↔ Runner：**内网 HTTP**，共享密钥 `MCP_RUNNER_TOKEN`。
- Runner ↔ 子进程：**stdin/stdout JSON-RPC**（MCP STDIO 传输），**不经 shell**。
- 子进程网络：MVP 默认 **`network_mode=deny`**（容器 `--network=none` 或等价策略）。

---

## 3. RunSpec 与校验

### 3.1 数据结构

```python
# app/tenant/mcp/runner/spec.py

class NetworkMode(str, Enum):
    DENY = "deny"       # MVP 默认
    ALLOW = "allow"     # 仅平台管理员模板可开

class RunSpec(BaseModel):
    tenant_id: UUID
    service_id: UUID
    actor_user_id: UUID | None = None
    command: str                    # 白名单：npx | node | python | python3
    args: list[str]                 # 长度上限 32，单项上限 512 字符
    env: dict[str, str] = {}        # 键值均须匹配 ^[A-Z_][A-Z0-9_]*$
    cwd: str | None = None          # MVP 禁止自定义 cwd（固定 /tmp/runner）
    max_runtime_sec: int = 30       # 1..120
    max_memory_mb: int = 512        # 256..2048，Runner 侧 cgroup/rlimit
    network_mode: NetworkMode = NetworkMode.DENY
    purpose: Literal["mcp_sync", "mcp_invoke", "script_exec"]  # 审计用
```

由 `McpService.connection_config` 生成：

```python
def build_run_spec(service: McpService, ctx: TenantContext, *, purpose: str) -> RunSpec:
    cfg = service.connection_config or {}
    return RunSpec(
        tenant_id=service.tenant_id,
        service_id=service.id,
        actor_user_id=ctx.user_id,
        command=cfg["command"],
        args=list(cfg.get("args") or []),
        env={k: str(v) for k, v in (cfg.get("env") or {}).items()},
        max_runtime_sec=min(int(cfg.get("timeout_sec", 30)), 120),
        network_mode=NetworkMode.DENY,
        purpose=purpose,
    )
```

### 3.2 校验规则（Runner 与 API 双重校验）

| 规则 | 说明 |
|------|------|
| command 白名单 | `npx`, `node`, `python`, `python3`；可配置扩展 |
| args 禁 shell 元字符 | 拒绝 `;` `\|` `&` `$` `` ` `` `>` `<` `\n` 等 |
| args 禁 path traversal | `..` 在 args 中拒绝（除 npx 包名 `@scope/pkg`） |
| env 键白名单模式 | 仅 `[A-Z_][A-Z0-9_]*`；值长度 ≤ 4096 |
| npx 包 | 可选：租户级「已批准包」列表（Phase 3b）；MVP 仅长度限制 |
| 并发 | 租户同时活跃 STDIO 会话 ≤ `MCP_RUNNER_MAX_CONCURRENT_PER_TENANT`（默认 3） |
| 全局并发 | Runner 总活跃会话 ≤ `MCP_RUNNER_MAX_CONCURRENT`（默认 20） |

---

## 4. MCP Runner 服务设计

### 4.1 部署形态

**推荐 MVP：独立 Docker 服务 `mcp-runner`**

```yaml
# docker/docker-compose.yml 新增
mcp-runner:
  build:
    context: ..
    dockerfile: docker/images/mcp-runner/Dockerfile
  container_name: milesai-mcp-runner
  environment:
    MCP_RUNNER_TOKEN: ${MCP_RUNNER_TOKEN}
    MCP_RUNNER_MAX_CONCURRENT: 20
    MCP_RUNNER_WORK_DIR: /var/run/mcp-runner
  networks:
    - milesai-net          # 仅被 api 访问，不对公网暴露
  ports: []                 # 不映射 host port；api 通过服务名访问
  read_only: true            # 根文件系统只读
  tmpfs:
    - /tmp:size=512M
  security_opt:
    - no-new-privileges:true
  cap_drop:
    - ALL
  restart: unless-stopped
```

Runner 镜像预装：`node`（供 npx）、`python3`；**不**预装任意 MCP 包（运行时 npx 拉取，MVP 网络 deny 时需改为「预装模板」或 Phase 3b 放开网络）。

> **MVP 网络策略说明：** `network_mode=deny` 与 `npx -y @pkg` 冲突。Phase 3a 采用 **预置命令模板**（镜像内已 `npm install -g` 常用 MCP）或 **租户提供本地 node 脚本路径**；`npx` 拉包放到 Phase 3b（`network_mode=allow` + 域名白名单）。

### 4.2 Runner HTTP API

内网专用，前缀 `/runner/v1`：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/sessions/mcp/list-tools` | 启动进程 → initialize → tools/list → 销毁 |
| POST | `/sessions/mcp/call-tool` | 启动进程 → initialize → tools/call → 销毁 |
| POST | `/sessions/script/exec` | 工具 v2 预留：执行受限 Python 片段 |

**请求示例（list-tools）：**

```json
{
  "run_spec": { "...": "RunSpec" },
  "connection_config": {
    "mcp_initialize": true,
    "timeout_sec": 30
  }
}
```

**响应：**

```json
{
  "ok": true,
  "tools": [{ "name": "...", "description": "...", "inputSchema": {} }],
  "session": {
    "duration_ms": 842,
    "exit_code": 0
  }
}
```

**错误：**

```json
{
  "ok": false,
  "error_code": "RUNTIME_TIMEOUT | INVALID_SPEC | PROCESS_CRASH | MCP_RPC_ERROR",
  "message": "...",
  "session": { "duration_ms": 30001, "exit_code": -9 }
}
```

### 4.3 STDIO MCP 协议实现（Runner 内部）

```text
SessionManager.run(spec, handler):
  1. validate_run_spec(spec)
  2. acquire_tenant_semaphore(spec.tenant_id)
  3. popen = execve(spec.command, spec.args, sanitized_env)  # 无 shell
     - preexec: setsid, setrlimit(RLIMIT_AS), optional prlimit
     - stdin/stdout/stderr 管道
  4. MCPStdioClient(stdin, stdout):
       - send initialize
       - optional notifications/initialized
       - handler(client)  → tools/list 或 tools/call
  5. 超时：SIGKILL 进程组
  6. release semaphore，写 audit
```

复用现有 JSON-RPC 解析：`app/tenant/mcp/rpc.py` 的 `parse_jsonrpc_result`、`normalize_tool_call_result`（Runner 作为独立进程可 import 同包或抽 `mcp_stdio` 共享库）。

### 4.4 API 侧 RunnerClient

```python
# app/tenant/mcp/runner/client.py

class RunnerClient:
    async def list_tools(self, spec: RunSpec, connection_config: dict) -> list[dict]: ...
    async def call_tool(self, spec: RunSpec, tool_name: str, arguments: dict, ...) -> dict: ...
```

配置：

```python
# app/core/config.py
mcp_runner_enabled: bool = False
mcp_runner_url: str = "http://mcp-runner:8090"
mcp_runner_token: str = ""
mcp_runner_max_concurrent_per_tenant: int = 3
```

`McpServiceManager.sync_service` 改造：

```python
if transport == "stdio":
    if not settings.mcp_runner_enabled:
        raise BadRequestError("STDIO 需要启用 MCP Runner，请联系管理员")
    spec = build_run_spec(row, self.ctx, purpose="mcp_sync")
    tools = await RunnerClient().list_tools(spec, row.connection_config)
    # 写 tools_cache，同 HTTP 路径
```

---

## 5. 数据模型与审计

### 5.1 新增表 `mcp_runner_sessions`（ORM + 001 迁移）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| tenant_id | UUID | |
| service_id | UUID | nullable（script 时为空） |
| actor_user_id | UUID | nullable |
| purpose | string | mcp_sync / mcp_invoke / script_exec |
| command | string | 摘要，不含完整 env 秘密 |
| args_digest | string | SHA256(args join) |
| status | string | success / error / timeout |
| exit_code | int | nullable |
| duration_ms | int | |
| error_message | text | nullable |
| tool_name | string | invoke 时 |
| created_at | timestamptz | |

索引：`(tenant_id, created_at DESC)`。

### 5.2 与现有审计的关系

| 事件 | 写入 |
|------|------|
| MCP HTTP/SSE invoke | 可选扩展 `tool_invocation_logs`（source=mcp） |
| MCP STDIO invoke | `mcp_runner_sessions` + `tool_invocation_logs` |
| 工具 script v2 | 同 Runner，`purpose=script_exec` |

---

## 6. 安全与威胁模型

| 威胁 | 缓解 |
|------|------|
| API 进程 RCE | API 不 exec；仅 HTTP 调 Runner |
| Runner 被伪造 | `MCP_RUNNER_TOKEN` + 内网隔离 + 不暴露 port |
| 命令注入 | `execve` 数组，禁 shell |
| 读宿主机文件 | Runner 容器 read-only root + 最小 volume |
| 出站攻击 / 挖矿 | MVP `network_mode=deny`；3b 域名白名单 |
| 资源耗尽 | 全局/租户 semaphore + timeout + memory limit |
| 跨租户逃逸 | RunSpec 强制 tenant_id；Runner 不持久化跨请求状态 |
| 供应链恶意 npm | MVP 预装模板；3b 包审批流 |

---

## 7. 配置项汇总

```bash
# API / Worker
MCP_RUNNER_ENABLED=true
MCP_RUNNER_URL=http://mcp-runner:8090
MCP_RUNNER_TOKEN=<random-32-bytes>
MCP_RUNNER_MAX_CONCURRENT_PER_TENANT=3

# Runner 进程
MCP_RUNNER_MAX_CONCURRENT=20
MCP_RUNNER_DEFAULT_TIMEOUT_SEC=30
MCP_RUNNER_DEFAULT_MEMORY_MB=512
MCP_RUNNER_COMMAND_WHITELIST=npx,node,python,python3
MCP_RUNNER_WORK_DIR=/tmp

# 已有
MCP_ALLOW_PRIVATE_HOSTS=false   # 生产
```

---

## 8. 代码结构（待建）

```text
backend/app/tenant/mcp/runner/
  __init__.py
  spec.py          # RunSpec 模型 + validate_run_spec + build_run_spec
  client.py        # API 侧 HTTP 客户端
  audit.py         # write_mcp_runner_session

backend/app/runner/              # Runner 独立入口（同 repo，独立 CMD）
  __init__.py
  main.py          # FastAPI / uvicorn，仅 /runner/v1
  session.py       # SessionManager, execve, timeout
  mcp_stdio.py     # initialize / tools/list / tools/call
  limits.py        # semaphore, rlimit

docker/images/mcp-runner/
  Dockerfile       # python + node，非 root user

backend/tests/
  test_runner_spec.py
  test_runner_session.py      # mock subprocess
  test_mcp_stdio_integration.py  # 可选：@modelcontextprotocol/server-everything
```

**与现有模块关系：**

| 现有 | 改造 |
|------|------|
| `mcp/services/mcp.py` | stdio 分支调 RunnerClient |
| `mcp/client.py` | 保持 HTTP/SSE；stdio 不进入 |
| `mcp/security.py` | 不变 |
| `deletion/tenant.py` | 删租户时清 `mcp_runner_sessions` |

---

## 9. 前端变更（小）

| 项 | 说明 |
|----|------|
| STDIO 卡片 | sync 成功后正常展示工具；失败展示 Runner 错误 |
| 创建 STDIO | 增加说明：「需平台启用 Runner；MVP 仅支持预置/本地命令」 |
| MCP invoke 试调用 | 无 UI 变更，后端通路打通即可 |

---

## 10. 实施分期

### Phase 3a（本方案 MVP，约 2 周）

- [ ] RunSpec 校验 + 单元测试
- [ ] Runner 服务骨架 + `list-tools` 会话
- [ ] API `RunnerClient` + `sync_service` stdio 分支
- [ ] docker-compose `mcp-runner`
- [ ] `mcp_runner_sessions` 审计表
- [ ] 集成测试：本地 `@modelcontextprotocol/server-everything` 或 mock stdio

### Phase 3b（+1 周）

- [ ] `call-tool` 会话（invoke 通路）
- [ ] 租户并发限制 + 队列/backpressure
- [ ] 可选：`network_mode=allow` + npm registry 域名白名单

### Phase 3c（工具 v2）

- [ ] `POST /sessions/script/exec`：受限 Python（AST 白名单或固定 wrapper）
- [ ] `tool_type=script` 创建 + 编辑器 UI
- [ ] 复用 RunSpec + SessionManager

---

## 11. 测试策略

| 层级 | 内容 |
|------|------|
| 单元 | RunSpec 校验、args 禁字符、semaphore |
| 组件 | Mock stdin/stdout 的 MCP JSON-RPC 往返 |
| 集成 | Docker Compose 起 api + runner，STDIO sync 真实 MCP server |
| 安全 | 尝试 `; rm -rf`、超长 args、并发打满 |
| 回归 | HTTP/SSE sync/invoke 不受影响 |

---

## 12. 风险与决策记录

| 决策 | 选项 | 结论 | 理由 |
|------|------|------|------|
| Runner 形态 | Celery 队列 vs 独立服务 | **独立 HTTP 服务** | 超时/杀进程需同步语义；sync 请求不宜排队过久 |
| MVP 网络 | deny vs allow npx | **deny + 预装 MCP** | 降低 SSRF/挖矿；npx 放 3b |
| 协议 | 自定义 vs MCP stdio | **标准 MCP stdio** | 与生态兼容 |
| 脚本 v2 | 同 Runner vs 独立 | **同 Runner** | 统一审计与资源限制 |

---

## 13. 验收标准

1. `MCP_RUNNER_ENABLED=true` 时，STDIO MCP 服务可 **sync** 出真实 `tools_cache`。
2. STDIO MCP 可 **invoke** 试调用，结果与 HTTP MCP 结构一致。
3. API 容器内 **无** `subprocess` 调用用户 command（代码审查 + grep）。
4. RunSpec 含 `;` 的 args 在 API 与 Runner 均被拒绝。
5. 单次会话超时后进程被终止，Runner 返回 `RUNTIME_TIMEOUT`。
6. `mcp_runner_sessions` 有成功/失败记录。
7. `MCP_RUNNER_ENABLED=false` 时行为与现网一致（STDIO 拒绝）。

---

## 14. 参考

- [MCP Sandbox 架构基线](../../architecture/mcp-sandbox.md)
- [MCP 服务指南](../../guides/mcp.md)
- [工具 v1 设计](./2026-05-25-tools-design.md) — v2 script 复用 Runner
- MCP STDIO Transport: https://modelcontextprotocol.io/specification/2025-03-26/basic/transports#stdio
