# 工具（Tools）指南

MilesAI **工具模块**管理租户可用的**平台内置工具**与**自定义 HTTP / Python 脚本工具**，供技能包引用、工作台试调用、以及智能体 **function calling** 自动执行。

**MCP 是独立模块**，不在工具目录中合并展示。二者关系见 [§6 与 MCP 的关系](#6-与-mcp-的关系)。

---

## 1. 能力范围

| 类型 | 存储 | 执行 | Agent 自动调用 |
|------|------|------|----------------|
| **内置** | 代码 `BUILTIN_REGISTRY` | `invoke_builtin` | ✅ |
| **自定义 HTTP** | `tool_tools` 表 | `invoke_custom_http` | ✅ |
| **脚本 script** | `tool_tools` 表 | MCP Runner `script/exec` | ✅（需 `MCP_RUNNER_ENABLED`） |

内置工具（v1）：

| slug | 说明 |
|------|------|
| `calculator` | 安全数学表达式 |
| `http_request` | 通用 HTTP 请求 |
| `knowledge_search` | 单知识库语义检索 |
| `get_current_datetime` | 当前日期时间 |

---

## 2. 数据模型

表：`tool_tools`（`app/tenant/tools/models.py`）

| 字段 | 说明 |
|------|------|
| `slug` | 租户内唯一编号，`snake_case` |
| `tool_type` | `http` 或 `script` |
| `parameters` | 输入参数 JSON schema |
| `config` | HTTP：url、method、headers、body_mode、timeout_sec、response_path |
| `require_confirmation` | 试调用 / Agent 执行前需用户确认 |
| `is_active` | 是否启用 |

审计：`tool_invocation_logs`（ORM 模型，随 `001` 迁移建表）

---

## 3. API

前缀：`/api/v1/tools`（`tools:read` / `tools:write`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/tools/catalog?source=&category_id=&tag_ids=` | **仅** builtin + custom |
| GET | `/tools` | 自定义工具分页 |
| GET | `/tools/builtin` | 内置注册表详情 |
| POST | `/tools` | 创建 HTTP 工具 |
| PATCH | `/tools/{id}` | 更新 |
| DELETE | `/tools/{id}` | 软删 |
| POST | `/tools/{slug}/invoke` | 试调用（支持确认流） |
| GET | `/tools/invocation-logs` | 调用审计 |

`source` 筛选：`builtin` | `custom`（**不含 mcp**）。

---

## 4. 执行链路

```text
试调用 / Agent tool_agent
  → invoke_tool_with_context
      → 内置：invoke_builtin
      → 自定义：validate_params → 模板 URL → httpx
      → require_confirmation → 返回 pending / 写 invocation_log
```

Agent 启用条件（`app/tenant/agents/services/agent.py`）：

- 智能体**未绑定知识库**（`kb_ids` 为空）
- `config.enable_tool_calling = true`
- 已配置大模型
- 可选 `config.tool_slugs` 白名单；未配置则加载全部 builtin + 活跃 custom HTTP

---

## 5. 前端

路径：`/workbench/tools`

- Tab：**工具列表** / **调用日志**
- 来源筛选：全部 / 内置 / 自定义
- 标签筛选、CRUD、试调用
- 顶部说明：外部 MCP 服务请前往 [MCP 工作台](/workbench/mcp)

智能体表单「工具与能力」步骤：

- **平台工具**：勾选 `enable_tool_calling` + 可选 `tool_slugs`（无 KB 时生效）
- **MCP 服务**：独立多选 `mcp_service_ids`（仅提示词注入，见下节）

---

## 6. 与 MCP 的关系

工具和 MCP **不是同一套系统**，职责分离、互补使用。

### 6.1 对比

| 维度 | 工具（Tools） | MCP |
|------|---------------|-----|
| **定位** | 平台托管、可控能力 | 对接外部 MCP Server |
| **注册** | 内置 registry + `tool_tools` | `tool_mcp_services` |
| **传输** | 无（直接 HTTP 执行） | HTTP / SSE / STDIO（Runner 沙箱） |
| **目录 API** | `GET /tools/catalog` | `GET /mcp` + sync `tools_cache` |
| **试调用** | `POST /tools/{slug}/invoke` | `POST /mcp/{id}/tools/{name}/invoke` |
| **Agent 自动执行** | ✅ function calling | ❌ 当前仅 prompt 注入 |
| **审计** | `tool_invocation_logs` | `mcp_runner_sessions`（STDIO） |

### 6.2 架构示意

```text
┌─────────────────────┐          ┌─────────────────────┐
│   工具工作台         │          │   MCP 工作台         │
│   /workbench/tools  │          │   /workbench/mcp    │
└──────────┬──────────┘          └──────────┬──────────┘
           │                                │
           ▼                                ▼
    tool_tools + registry            tool_mcp_services
           │                                │
           ▼                                ▼
    invoke_tool_with_context         McpServiceManager
           │                                │
           └──────── Agent ────────────────┘
                 ├─ tool_slugs → tool_agent（真调用）
                 └─ mcp_service_ids → prompt 文本（仅说明）
```

### 6.3 何时用哪个

| 场景 | 推荐 |
|------|------|
| 调租户自己的 REST API | **自定义 HTTP 工具** |
| 轻量 Python 逻辑（无 import） | **脚本工具**（Runner 沙箱） |
| 计算器、查 KB、取时间 | **内置工具** |
| 接 GitHub / Filesystem 等 MCP 生态 | **MCP 服务** |
| Agent 对话里 LLM 自动调 | **工具**（`enable_tool_calling`） |
| 让 Agent「知道」MCP 有哪些能力 | **MCP 绑定**（提示词） |
| 高敏感 / 任意进程（npx） | **MCP STDIO + Runner** |

### 6.4 技能包

技能包 `tool_names` 存的是**工具 slug**（builtin 或 custom），与 MCP 无关。MCP 通过智能体 `config.mcp_service_ids` 单独绑定。

### 6.5 脚本工具（v2）

- `tool_type=script`，`config`: `{ "language": "python", "source": "...", "timeout_sec": 30 }`
- 用户须定义 `def run(params: dict) -> dict`；创建时 AST 校验，禁止 `import` / `eval` 等
- 执行走 [MCP Runner 沙箱](./mcp.md#8-mcp-runner-部署stdio-沙箱) `POST /runner/v1/sessions/script/exec`；API 进程不 subprocess
- 审计：`mcp_runner_sessions.purpose=script_exec` + `tool_invocation_logs`

### 6.6 后续演进

- **Agent 自动调 MCP**：独立迭代，将把 MCP `tools/call` 注册为 LangChain Tool（当前未实现）

---

## 7. 相关文档

- [MCP 服务指南](./mcp.md)
- [MCP Runner 沙箱](../architecture/mcp-sandbox.md)
- [工具 v1 设计规格](../superpowers/specs/2026-05-25-tools-design.md)
