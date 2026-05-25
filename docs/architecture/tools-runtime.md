# 工具运行时架构（目标方案）

**日期：** 2026-05-25  
**状态：** 目标架构（部分已落地，见 §8 对照）  
**读者：** 产品、后端、前端  
**关联：** [tools.md](../guides/tools.md)（实现与 API）、[mcp-sandbox.md](./mcp-sandbox.md)、[mcp.md](../guides/mcp.md)

---

## 1. 定位与原则

MilesAI 是**企业级多租户 AI 中台**（RAG、流程编排、智能体、合规隔离），工具设计服务于：

- **低代码**：租户管理员通过工作台配置能力，而非在平台内编写完整 Python 项目
- **Agent 真调用**：智能体通过 function calling **自动执行**已绑定工具
- **安全可审计**：多租户隔离、SSRF 防护、确认策略、调用日志、Runner 沙箱

### 1.1 用户心智（一句话）

> **工具 = 智能体可以自动调用的能力**；来源可以是平台内置、租户配置的 HTTP/变换脚本、或已接入 MCP 服务同步出的 tools。

### 1.2 设计原则

| 原则 | 说明 |
|------|------|
| **统一执行平面** | Agent / 流程 / 试调用均走同一套 `invoke` 链路与审计 |
| **管理面可分离、运行面须统一** | MCP 可在独立工作台注册；Agent 侧必须能 **call**，不能仅 prompt 说明 |
| **自定义主路径是 HTTP** | 业务逻辑在客户自有 API；平台做代理、校验与日志 |
| **脚本是补充，不是通用 Python** | 变换脚本用于 params→dict 轻量逻辑，非 bash/文件/任意 import |
| **内置是产品能力** | 由发版维护，与 RAG、合规等企业场景对齐 |
| **不追求超级 Agent 沙箱** | 完整 Shell/文件/社区 Python 包 → MCP + Runner，非工具模块主责 |

---

## 2. 三层能力模型

```text
┌─────────────────────────────────────────────────────────────┐
│  消费层：智能体 · 技能包 · 流程节点（未来）                      │
│  enable_tool_calling · tool_slugs · skill.tool_names         │
└─────────────────────────────┬───────────────────────────────┘
                              │ invoke_tool(name, params)
┌─────────────────────────────▼───────────────────────────────┐
│  Tool Runtime（执行平面）                                     │
│  参数校验 · 确认策略 · 租户隔离 · 审计 · 限流（规划）            │
└───────┬─────────────────┬─────────────────┬───────────────────┘
        ▼                 ▼                 ▼
   平台内置           租户集成            外部 MCP
   Built-in          Custom              MCP Tools
```

### 2.1 平台内置（Built-in）

| 项 | 说明 |
|----|------|
| **存储** | 代码 `BUILTIN_REGISTRY`（`tenant/tools/builtin_registry.py`），不入库 |
| **执行** | `invoke_builtin` → 复用现有 `tenant/*` Service（RAG、合规、附件等） |
| **扩展** | 发版新增；租户**不可改实现**，可按租户/智能体**启用** |
| **租户使用** | 与自定义工具相同：`tool_slugs` 白名单、试调用、调用日志、`require_confirmation` |
| **现状 slug** | `calculator`、`http_request`、`knowledge_search`、`get_current_datetime`（偏 **L1 轻量**） |

**推荐方向：系统内置一批「复杂工具」（L2）**，把已在平台内实现的能力（多库检索、合规检测、附件查询等）封装为 Agent 可调用的 builtin，租户**直接选用**即可，无需每个租户重复配 HTTP 或写脚本。

#### 2.1.1 轻量 vs 复杂内置

| 层级 | 特征 | 示例 | 租户感知 |
|------|------|------|----------|
| **L1 轻量** | 无状态、毫秒级、参数少 | `calculator`、`get_current_datetime` | 通用小工具 |
| **L2 复杂** | 调平台子系统、可能异步/耗资源、需租户上下文 | 多库检索、合规检测、列附件、触发流程 | **「平台能力一键给 Agent」** |

复杂内置与 **租户 HTTP 工具** 的分工：

| | 内置复杂工具 | 租户 HTTP 工具 |
|---|-------------|----------------|
| **谁实现** | 平台发版 | 租户自有 API |
| **谁运维** | 平台（升级、限流、安全） | 租户 |
| **典型能力** | RAG、合规、附件、流程 | CRM、ERP、内部微服务 |
| **配置** | 选 slug + 参数（如 `kb_id`） | 配 URL + schema |

复杂内置与 **MCP** 的分工：

| | 内置复杂工具 | MCP |
|---|-------------|-----|
| **依赖** | 平台已部署模块 | 外部 Server / npx |
| **体验** | 开箱即用、审计统一 | 生态丰富、需注册同步 |
| **适用** | 企业版核心能力（KB、合规） | GitHub、Filesystem 等标准协议 |

#### 2.1.2 候选目录（按现有模块映射）

以下为建议 slug（实现时以 `BUILTIN_REGISTRY` + `invoke_builtin` 为准）：

| 优先级 | slug（建议） | 能力 | 复用代码 | 默认确认 |
|--------|--------------|------|----------|----------|
| P1 | `knowledge_search` | 单库检索 | 已有 | 否 |
| P1 | `knowledge_search_multi` | 多库 / 混合检索 | `rag/retrieve`、Agent KB 绑定 | 否 |
| P1 | `compliance_check_text` | 敏感词/策略检测 | `ComplianceService.check_*` | 否 |
| P2 | `list_knowledge_bases` | 列出本租户 KB | `tenant/kb` | 否 |
| P2 | `get_attachment_meta` | 附件元数据 | `tenant/attachments` | 否 |
| P2 | `invoke_tenant_hook` | 触发已注册 HTTP 钩子 | `tenant/hooks` | **是** |
| P3 | `run_flow_once` | 单次执行已发布流程 | `flow_runtime` | **是** |
| P3 | `http_request` | 通用外呼（SSRF 防护） | 已有；建议弱化宣传 | 可选 |

**不宜做成内置复杂工具**（仍走 MCP 或专属页面）：

- 任意 Shell、读写租户服务器文件
- 未集成的第三方 SaaS（应用市场模板、外部 A2A 除非封装）
- 需租户自填 API Key 的云端搜网（可做成**可选插件** + 平台配置，非默认 builtin）

#### 2.1.3 治理与开关（复杂工具必备）

复杂工具上线须带治理字段（可扩展 registry 元数据，无需入库）：

```python
# builtin_registry 条目建议字段（规划）
{
    "slug": "compliance_check_text",
    "tier": "complex",           # light | complex
    "require_confirmation": False,
    "tenant_toggle": True,       # 是否允许租户在智能体里勾选
    "platform_only": False,      # True 时仅运营开关，租户不可见
    "rate_limit_key": "compliance",
    "max_timeout_sec": 30,
}
```

| 机制 | 说明 |
|------|------|
| **租户可见** | 工具列表 `source=builtin` 展示；复杂工具带「平台」标签 |
| **按智能体启用** | `tool_slugs` 白名单；未勾选则不出现在 function schema |
| **按租户套餐（可选）** | 未来 `tenant.config.enabled_builtin_slugs` 或套餐位 |
| **确认策略** | 写操作、外呼、流程类默认 `require_confirmation=true` |
| **限流与配额** | 复杂工具单独计数（检索条数、合规 QPS） |
| **审计** | 统一 `tool_invocation_logs`，`source=builtin` |

#### 2.1.4 实现模式（保持一套 Runtime）

```text
BUILTIN_REGISTRY  （元数据 + schema）
       ↓
integrations/langchain/tools.py  → StructuredTool（Agent）
       ↓
invoke_builtin(slug, params)    → 分发到各 Service
       ├─ knowledge_search      → search_kb / load_kb
       ├─ compliance_check_text → ComplianceService
       ├─ list_knowledge_bases  → KbService.list...
       └─ ...
```

原则：

- **不**为每个复杂工具新建 HTTP 路由；统一 `POST /tools/{slug}/invoke`
- **不**把实现塞进租户 `tool_tools` 表
- 复杂逻辑留在现有 Service，builtin 只做**薄适配层**（参数校验 + 调用 + 结果整形）

### 2.2 租户集成（Custom）

| 子类型 | 存储 | 执行 | 定位 |
|--------|------|------|------|
| **HTTP** | `tool_tools`，`tool_type=http` | `invoke_custom_http` | **主路径**：REST 代理 + 参数模板 |
| **变换脚本** | `tool_tools`，`tool_type=script` | Runner `script/exec` | **辅路径**：无 import 的 `run(params)->dict` |

**HTTP 工具**：url、method、headers、body_mode、timeout_sec、response_path；URL/Headers 支持 `{{param}}` 模板。

**变换脚本**（当前 v2）：

- 须定义 `run(params: dict) -> dict`
- AST 校验：禁止 `import`、`eval`、`open` 等
- 适用：格式化、过滤、简单算术、字段映射
- 不适用：联网、读写盘、复杂 JSON/正则（规划 v2.1 预注入 `json`/`re`/`datetime`/`math`）

### 2.3 外部 MCP（MCP Tools）

| 项 | 说明 |
|----|------|
| **存储** | `tool_mcp_services` + 同步后的 `tools_cache` |
| **传输** | HTTP / SSE / STDIO（STDIO 经 [MCP Runner](./mcp-sandbox.md)） |
| **管理 UI** | `/workbench/mcp`（独立 CRUD、同步、试调用） |
| **目标：Agent 调用** | 绑定 MCP 后，将其 tools **动态注册**为可调用 Tool（见 §4） |

---

## 3. 统一 Tool Runtime

### 3.1 入口

```text
POST /tools/{slug}/invoke          # 试调用（工作台）
invoke_tool_with_context(...)      # Agent tool_agent、确认流、日志
```

### 3.2 分发逻辑（目标）

```text
resolve_tool_meta(name, tool_id?)
  ├─ source=builtin     → invoke_builtin
  ├─ source=custom      → tool_type=http | script
  └─ source=mcp         → McpServiceManager.invoke_tool（规划）

require_confirmation? → pending / 用户确认后继续
write_tool_invocation_log（+ MCP 时关联 runner session）
```

### 3.3 横切能力

| 能力 | 说明 |
|------|------|
| **租户隔离** | 所有 custom / MCP 按 `tenant_id` |
| **SSRF** | HTTP 工具 + 内置 `http_request` |
| **确认** | `require_confirmation`；写操作、敏感 MCP 建议开启 |
| **审计** | `tool_invocation_logs`；STDIO/脚本另写 `mcp_runner_sessions` |
| **权限** | `tools:read` / `tools:write`；MCP 独立权限保留 |

---

## 4. Agent 绑定模型（目标）

### 4.1 配置语义

```yaml
# agent.config（目标语义，字段名可与现网略有差异）
enable_tool_calling: true

# 平台工具白名单；空表示启用全部 builtin + 活跃 custom
tool_slugs: ["calculator", "weather_api", "transform_script"]

# 绑定的 MCP 服务；同步后 tools 进入 Agent 可调用集合
mcp_service_ids: ["uuid-1", "uuid-2"]
```

### 4.2 MCP 工具命名（规划）

避免与 builtin/custom slug 冲突，建议：

```text
mcp.{service_slug}.{tool_name}
# 例：mcp.github.create_issue
```

解析时：`source=mcp`，携带 `service_id` + `tool_name`。

### 4.3 与 RAG 的关系（目标）

| 阶段 | 行为 |
|------|------|
| **现状** | 智能体绑定 KB 时优先 `_rag_chat`，与 `tool_agent` 路径互斥 |
| **目标** | **RAG 与 tools 可并存**：`knowledge_search` 作为内置工具之一，LLM 自行决定是否检索 |

### 4.4 与技能包

- `skill.tool_names`：引用 **builtin / custom** 的 slug
- MCP：通过智能体 `mcp_service_ids` 绑定；技能包可不重复列举 MCP tool 名（或未来支持 `mcp:` 前缀引用）

---

## 5. 管理面 vs 运行面

| 维度 | 管理面（工作台） | 运行面（Agent） |
|------|------------------|-----------------|
| **内置工具** | 工具列表只读展示 | 可 call |
| **HTTP / 脚本** | `/workbench/tools` CRUD | 可 call |
| **MCP** | `/workbench/mcp` 注册与同步 | **目标：可 call**；现状：仅 prompt 注入 |
| **Catalog API** | `GET /tools/catalog` 仅 builtin+custom | Agent 加载 = catalog + 展开 MCP tools |

**刻意不做**：把 MCP 行塞进 `tool_tools` 表做 CRUD——生命周期与传输层不同，管理 UI 分离更清晰。

---

## 6. 场景选型

| 场景 | 推荐 |
|------|------|
| 调租户自己的 REST API | **HTTP 工具** |
| 对 params 做映射/过滤/简单计算 | **变换脚本** |
| 计算器、时间、单库检索 | **内置 L1** |
| **多库检索、合规、附件、流程等企业能力** | **内置 L2 复杂工具**（推荐扩展方向） |
| GitHub、Filesystem、社区 MCP | **MCP 服务** |
| Agent 对话自动执行 | **统一 Tool Runtime**（builtin + custom + MCP） |
| 任意 Shell、读写容器文件 | **MCP + Runner / 外部 Sandbox**（非工具模块主责） |
| 租户在线写完整 Python 包 | **不推荐**；业务 API + HTTP 工具 |

---

## 7. 演进路线

### P0 — 对齐「内置 + 自定义 + MCP 均可调用」

| 项 | 说明 |
|----|------|
| Agent 自动调 MCP | `tools_cache` → LangChain StructuredTool → `invoke` 走 MCP client |
| 文档与 UI 文案 | 四类能力边界；脚本称「变换脚本」 |
| 审计统一 | MCP 调用可选写入 `tool_invocation_logs`（`source=mcp`） |

### P1 — 提升自定义与 RAG 协同

| 项 | 说明 |
|----|------|
| 脚本预注入 stdlib | Runner 注入 `json`、`datetime`、`re`、`math`；仍禁用户 `import` |
| RAG + tools 共存 | 有 KB 时仍可 function calling |
| **内置复杂工具（首批）** | `compliance_check_text`、`list_knowledge_bases`、增强 `knowledge_search` |
| 工具分组/标签 | 工作台区分 L1/L2 内置 |

### P2 — 平台厚度

| 项 | 说明 |
|----|------|
| 内置复杂工具（扩展） | 附件、流程单次执行、钩子触发等 |
| 租户套餐级 builtin 开关 | `tenant_toggle` / 套餐位 |
| 调用限流 | 租户级 QPS / 复杂工具配额 |
| 流程节点 | 复用同一 Runtime |

### 明确不做（短期）

- 租户在 UI 内编写任意 import 的 Python 工程
- 平台内置 bash / 通用文件系统工具（与 MCP/AIO Sandbox 产品线区分）

---

## 8. 现状对照（2026-05）

| 能力 | 状态 |
|------|------|
| builtin + custom HTTP catalog & invoke | ✅ |
| 变换脚本 v2（Runner、AST 校验） | ✅ |
| `tool_invocation_logs`、确认策略 | ✅ |
| Agent `tool_agent`（builtin + custom） | ✅（无 KB 时） |
| MCP 独立工作台、sync、试调用 | ✅ |
| MCP → Agent function calling | ❌ 规划 P0 |
| 脚本预注入 stdlib | ❌ 规划 P1 |
| RAG 与 tool calling 共存 | ❌ 规划 P1 |

代码入口：

| 模块 | 路径 |
|------|------|
| 工具 Service / API | `backend/app/tenant/tools/` |
| 执行 | `tenant/tools/invoke.py` |
| LangChain 加载 | `integrations/langchain/tools.py`、`tool_agent.py` |
| MCP | `backend/app/tenant/mcp/` |
| Runner | `backend/app/runner/` |

---

## 9. 相关文档

- [工具指南（API 与现网行为）](../guides/tools.md)
- [MCP 服务指南](../guides/mcp.md)
- [MCP Runner 沙箱](./mcp-sandbox.md)
- [工具 v1 历史规格](../superpowers/specs/2026-05-25-tools-design.md)
