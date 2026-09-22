# 工具（Tools）指南

**功能规格：** [features/tools-mcp-skills.md](../features/tools-mcp-skills.md)

MilesAI **工具模块**管理租户可用的**平台内置工具**（含 **L2 复杂内置**，如 `knowledge_search`、`generate_*`）与**自定义 HTTP / 变换脚本工具**，供技能包引用、工作台试调用、以及智能体 **function calling** 自动执行。

**内置复杂工具**（多库检索、合规检测等，平台实现、租户选用）见 **[工具运行时架构 §2.1](../architecture/tools-runtime.md#21-平台内置built-in)**。

**目标架构**（统一执行平面、MCP 纳入 Agent 调用等）见 **[工具运行时架构](../architecture/tools-runtime.md)**。本文描述**当前实现**与 API；与目标差异见该文档 §8。

**MCP 管理**在独立工作台；与工具的关系见 [§6](#6-与-mcp-的关系)。

---

## 1. 能力范围

| 类型 | 存储 | 执行 | Agent 自动调用 |
|------|------|------|----------------|
| **内置** | 代码 `BUILTIN_REGISTRY` | `invoke_builtin` | ✅ |
| **自定义 HTTP** | `tool_tools` 表 | `invoke_custom_http` | ✅ |
| **变换脚本 script** | `tool_tools` 表 | MCP Runner `script/exec` | ✅（需 `MCP_RUNNER_ENABLED`） |
| **MCP tools** | `tool_mcp_services.tools_cache` | `McpServiceManager.invoke_tool` | ✅ 绑定 `config.mcp_service_ids` 后按 `mcp__{service}__{tool}` 纳入 function calling |

内置工具（v1）：

| slug | 说明 |
|------|------|
| `calculator` | 安全数学表达式 |
| `http_request` | 通用 HTTP 请求 |
| `knowledge_search` | 知识库语义检索（单库/多库；可省略 kb 用智能体绑定库） |
| `get_current_datetime` | 当前日期时间 |
| `web_search` | DuckDuckGo 网页搜索（opt-in） |
| `code_execution` | Runner 沙箱执行 Python 片段（opt-in） |
| `compliance_check_text` | 租户敏感词检测（只读，不写拦截审计；opt-in） |
| `run_flow_once` | 触发本租户已发布流程一次（需确认，带递归/超时护栏；opt-in） |
| `invoke_tenant_hook` | 手动触发已绑定 HTTP 钩子链（需确认，仅 HTTP；opt-in） |
| `generate_image` / `generate_video` / `generate_speech` | 生成物（`generative_only`） |
| `skill_read_reference` / `skill_run_script` | 技能包引用与脚本（`skill_bound_only`） |

> **opt-in**：registry 标 `opt_in: True` 的工具默认不进入 function schema，须在智能体 `config.tool_slugs`
> 显式勾选（避免 `tool_slugs` 为空时默认放开外呼/执行能力）。基线工具（`calculator`、`http_request`、
> `get_current_datetime`、`knowledge_search`）始终可用。

---

## 2. 数据模型

表：`tool_tools`（`backend/packages/miles-portal/src/miles_portal/tenant/tools/models.py`）

| 字段 | 说明 |
|------|------|
| `slug` | 租户内唯一编号，`snake_case` |
| `tool_type` | `http` 或 `script` |
| `parameters` | 输入参数 JSON schema |
| `config` | HTTP：url、method、headers、body_mode、timeout_sec、response_path；script：source、timeout_sec |
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
| POST | `/tools` | 创建 HTTP / 脚本工具 |
| PATCH | `/tools/{id}` | 更新 |
| DELETE | `/tools/{id}` | 软删 |
| POST | `/tools/{slug}/invoke` | 试调用（支持确认流） |
| GET | `/tools/invocation-logs` | 调用审计 |

`source` 筛选：`builtin` | `custom`（**不含 mcp**；MCP 见 `/mcp`）。

---

## 4. 执行链路

```text
试调用 / Agent tool_agent
  → invoke_tool_with_context
      → 内置：invoke_builtin
      → HTTP：validate_params → 模板 URL → httpx
      → 脚本：Runner script/exec
      → require_confirmation → 返回 pending / 写 invocation_log
```

Agent 启用条件（`backend/packages/miles-portal/src/miles_portal/tenant/agents/services/agent/`）：

- `config.enable_tool_calling = true`（或 `enable_generative_tools`）
- 已配置大模型
- 可选 `config.tool_slugs` 白名单；未配置则加载**基线** builtin（`calculator`/`http_request`/`get_current_datetime`/`knowledge_search`）
  + 活跃 custom（HTTP + script）；配置后按白名单过滤
  - **opt-in 内置**（`web_search` / `code_execution` / `compliance_check_text` / `run_flow_once` / `invoke_tenant_hook`）
    仅在白名单显式勾选时注入，未勾选不进入 function schema（system prompt 摘要同集合）
- 可选 `config.mcp_service_ids`：绑定 MCP 服务的 tools 一并可调用
- **绑定知识库时与 RAG 共存**：`knowledge_search` 强制加入工具集（不受白名单约束），
  命中片段回填 `ChatResponse.sources`，由模型自行决定是否检索

---

## 5. 前端

路径：`/workbench/tools`

- Tab：**工具列表** / **调用日志**
- 来源筛选：全部 / 内置 / 自定义
- 创建/编辑：sheet 布局；HTTP / Python 变换脚本
- 顶部说明：外部 MCP 服务请前往 MCP 工作台（`/workbench/mcp`）

智能体表单「工具与能力」步骤：

- **平台工具**：`enable_tool_calling` + 可选 `tool_slugs`
- **MCP 服务**：`mcp_service_ids`（**现状**：仅提示词注入；**目标**：自动 function calling）

---

## 6. 与 MCP 的关系

### 6.1 设计分工

| 维度 | 工具（Tools） | MCP |
|------|---------------|-----|
| **定位** | 平台托管 + 租户 HTTP/脚本 | 外部 MCP Server 生态 |
| **管理 UI** | `/workbench/tools` | `/workbench/mcp` |
| **Catalog API** | `GET /tools/catalog` | `GET /mcp` + sync |
| **Agent 执行** | ✅ function calling | ✅ 绑定后同样 function calling |

详见 [工具运行时架构 §5](../architecture/tools-runtime.md#5-管理面-vs-运行面)。

### 6.2 架构示意

```text
Agent
  └─ Tool Runtime
        ├─ builtin / custom（tool_slugs 白名单）
        └─ mcp__{service}__{tool}（mcp_service_ids 绑定服务展开）
              → 只读工具免确认；其余需用户确认
```

### 6.3 何时用哪个

| 场景 | 推荐 |
|------|------|
| 调租户自己的 REST API | **HTTP 工具** |
| params 映射、过滤、简单计算 | **变换脚本** |
| 计算器、查 KB、取时间 | **内置工具** |
| GitHub / Filesystem 等 MCP 生态 | **MCP 服务** |
| Agent 自动调外部能力 | **目标：HTTP + MCP 均可** |

### 6.4 技能包

技能包 `tool_names` 存 **工具 slug**（builtin 或 custom）。MCP 通过智能体 `mcp_service_ids` 单独绑定。

### 6.5 变换脚本（v2）

- `tool_type=script`，`config`: `{ "language": "python", "source": "...", "timeout_sec": 30 }`
- 须定义 `def run(params: dict) -> dict`；禁止用户 `import` / `eval` 等
- **预注入 stdlib**：Runner 提供 `json`、`re`、`math`、`datetime`，脚本直接引用即可
- **能力边界**：轻量变换，非通用 Python；详见 [架构 §2.2](../architecture/tools-runtime.md#22-租户集成custom)
- 执行：`POST /runner/v1/sessions/script/exec`
- 审计：`mcp_runner_sessions.purpose=script_exec` + `tool_invocation_logs`

---

## 7. 相关文档

- **[工具运行时架构（目标方案）](../architecture/tools-runtime.md)**
- [MCP 服务指南](./mcp.md)
- [MCP Runner 沙箱](../architecture/mcp-sandbox.md)

---

## 8. LangChain toolkit（L3 schema 壳）

内置工具的 **function-calling schema** 与租户侧执行分离：

| 层 | 路径 | 职责 |
|----|------|------|
| L3 schema | `miles_integrations/langchain/toolkit/` | `catalog._DECLS` 声明表 + `naming` / `inputs` / `specs`；按 slug 查表，**从不遍历** `_DECLS` |
| 分组集合 | 同文件 `_PLATFORM_SLUGS` / `_OPT_IN_SLUGS` / `_SKILL_SLUGS` / `_GENERATIVE_SLUGS` | 未归组的声明不会出现在任何工具列表（静默） |
| 租户元数据 | `tenant/tools/builtin_registry.py` | 展示名、opt-in、确认策略 |
| 执行 | `tenant/tools/handlers/` | 真正调用（HTTP / 检索 / 生成等） |

新增内置工具：先在 `_DECLS` 加壳并归入某一分组 → registry → handler。双向一致性由 `tests/miles_integrations/langchain/test_toolkit_contract.py` 钉住。目录总览见 [ai-stack.md](./ai-stack.md)。
