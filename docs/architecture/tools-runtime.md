# 工具运行时架构（目标方案）

**状态：** 目标架构（部分已落地，见 §8 对照）  
**As-Is 规格：** [features/tools-mcp-skills.md](../features/tools-mcp-skills.md) · **现网 API：** [guides/tools.md](../guides/tools.md)  
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
| **现状 slug** | L1 轻量：`calculator`、`http_request`、`get_current_datetime`、`web_search`；L2 复杂：`knowledge_search`、`compliance_check_text`、`code_execution`、`run_flow_once`、`invoke_tenant_hook`、`generate_*`、`skill_read_reference` / `skill_run_script` |

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
| ✅ | `knowledge_search` | 知识库检索（单库/多库、混合/rerank；省略 kb 用绑定库） | 已有 | 否 |
| ✅ | `compliance_check_text` | 敏感词检测（只读，不写拦截审计） | `CompliancePipeline` + `load_tenant_scan_words` | 否 |
| ✅ | `run_flow_once` | 触发本租户**已发布**流程一次 | `FlowService.run` + 递归/超时护栏 | **是** |
| ✅ | `invoke_tenant_hook` | 手动触发已绑定 **HTTP** 钩子链 | `HookExecutor.run_manual_http` | **是** |
| 不做 | `list_knowledge_bases` | 列出本租户 KB | — | — （绑定 KB 的 `kb_ids` 已注入 system prompt，工具冗余） |
| 缓做 | `get_attachment_meta` | 附件元数据 | `tenant/attachments` | 否（需先有「当前会话/资源范围」语义，否则会列出整租户附件） |
| P3 | `http_request` | 通用外呼（SSRF 防护） | 已有；建议弱化宣传 | 可选 |

`run_flow_once` 的护栏（实现于 `tenant/tools/services/flow_once.py`）：

- **仅已发布**：`FlowStatus.PUBLISHED` 且 `current_version > 0`，草稿不可被 Agent 触发；
- **仅本租户**：`FlowRepository` + `assert_tenant_access`；
- **递归防护**：`ContextVar` 计数嵌套触发，超过 `MAX_FLOW_ONCE_DEPTH`（2）拒绝——
  流程内 `PlatformTool` 节点默认 `confirmed=True`，故无此护栏会无限递归；
- **超时**：`asyncio.wait_for` 默认 120s、上限 300s；执行复用 `FlowService.run`
  （合规扫描 + FLOW 级 Hook + 审计一致）。

`invoke_tenant_hook` 的边界（实现于 `tenant/hooks/services/executor/service.py`
的 `run_manual_http` + `tenant/tools/services/hook_once.py`）：

- **仅 HTTP**：跳过 Python 钩子（工具调用不执行平台插件代码）；
- **仅本租户**：`HookExecutor` 以 `tenant_id` 过滤绑定；按 `trigger` + `scope`
  （+ 可选 `target_id`）匹配，`priority` 升序串行；
- **不抛阻断**：`block` / `on_failure=fail_request` 作为结果项返回，不中断对话；
- **结果可用**：附带截断响应体（≤4000 字符）与 `modify` 后的 `payload`；
- 执行同样写入 `hook_execution_logs`。

**不宜做成内置复杂工具**（仍走 MCP 或专属页面）：

- 任意 Shell、读写租户服务器文件
- 未集成的第三方 SaaS（应用市场模板、外部 A2A 除非封装）
- 需租户自填 API Key 的云端搜网（可做成**可选插件** + 平台配置，非默认 builtin）

#### 2.1.3 启用与治理

**opt-in 机制**：外呼/执行类 L2 工具在 registry 标 `opt_in: True`，**默认不进入 function schema**，
须在 `agent.config.tool_slugs` 显式勾选才注入。原因：`tool_slugs` 为空时白名单不生效（= 全部），
若把 `run_flow_once` / `invoke_tenant_hook` 直接放进基线列表，会对所有智能体默认放开执行与外呼能力。

| 集合 | 内容 | 注入条件 |
|------|------|----------|
| **基线** | `calculator`、`http_request`、`get_current_datetime`、`knowledge_search` | 始终 |
| **opt-in** | `web_search`、`code_execution`、`compliance_check_text`、`run_flow_once`、`invoke_tenant_hook` | 出现在 `tool_slugs` 时 |
| **技能壳** | `skill_read_reference`、`skill_run_script` | `config.skill_package_id` |
| **生成壳** | `generate_image/video/speech` | `config.enable_generative_tools` |
| **MCP** | `mcp__{service}__{tool}` | `config.mcp_service_ids` |

system prompt 的内置工具摘要（`agents/services/context.py`）与 function schema 同集合：
未勾选的 opt-in、未开启的 `generative_only` 均不宣传，避免 LLM 调用不存在的工具。

| 机制 | 说明 |
|------|------|
| **租户可见** | 工具列表 `source=builtin` 展示；复杂工具带「平台」标签 |
| **按智能体启用** | 基线常驻；opt-in 走 `tool_slugs` 白名单 |
| **按租户套餐（可选）** | 未来 `tenant.config.enabled_builtin_slugs` 或套餐位 |
| **确认策略** | 写操作、外呼、执行、流程类默认 `require_confirmation=true` |
| **限流与配额** | 复杂工具单独计数（检索条数、合规 QPS） |
| **审计** | 统一 `tool_invocation_logs`，`source=builtin` |

复杂工具上线还可扩展 registry 治理字段（无需入库）：

```python
# builtin_registry 条目可选治理字段（规划）
{
    "slug": "compliance_check_text",
    "tier": "complex",           # light | complex
    "platform_only": False,      # True 时仅运营开关，租户不可见
    "rate_limit_key": "compliance",
    "max_timeout_sec": 30,
}
```

#### 2.1.4 实现模式（保持一套 Runtime）

```text
BUILTIN_REGISTRY  （元数据 + schema）
       ↓
integrations/langchain/toolkit/catalog.py  → StructuredTool（Agent）
       ↓
    invoke_builtin(slug, params)    → 分发到各 Service
       ├─ knowledge_search      → rag.generate.retrieve_hits（多库 + 各库 hybrid/rerank）
       ├─ compliance_check_text → CompliancePipeline.scan（租户词库，只读）
       ├─ run_flow_once         → FlowService.run（已发布流程 + 递归/超时护栏）
       └─ invoke_tenant_hook    → HookExecutor.run_manual_http（仅 HTTP 钩子）
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
- Runner 预注入白名单 stdlib：`json`、`re`、`math`、`datetime`，脚本直接引用即可（**不开放** `import`）
- 适用：格式化、过滤、简单算术、字段映射、正则解析、时间处理
- 不适用：联网、读写盘、需要白名单外模块

### 2.3 外部 MCP（MCP Tools）

| 项 | 说明 |
|----|------|
| **存储** | `tool_mcp_services` + 同步后的 `tools_cache` |
| **传输** | HTTP / SSE / STDIO（STDIO 经 [MCP Runner](./mcp-sandbox.md)） |
| **管理 UI** | `/workbench/mcp`（独立 CRUD、同步、试调用） |
| **Agent 调用** | 绑定 MCP 后，其 tools 动态注册为可调用 Tool（function name `mcp__{service}__{tool}`） |

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
  └─ source=mcp         → McpServiceManager.invoke_tool

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

### 4.2 MCP 工具命名

避免与 builtin/custom slug 冲突，组合为 LLM 合法的 function name：

```text
mcp__{service}__{tool_name}
# 例：mcp__github__create_issue
```

- 服务/工具名做标识符清洗；含中文等有损清洗时给服务名追加 4 位哈希防塌缩碰撞
- 整体超 64 字符时截断并追加 6 位摘要（OpenAI function name 上限）
- 解析时按租户服务列表重新组合匹配，`source=mcp`，携带 `service_id` + 原始 `tool_name`

### 4.3 与 RAG 的关系

绑定 KB 且开启工具调用时走 `tool_agent`：`knowledge_search` 作为内置工具之一，
由 LLM 自行决定是否检索（`kb_ids` 可省略，默认检索智能体绑定的全部知识库），
命中片段回填 `ChatResponse.sources`。未开启工具调用时仍走 LangGraph / `generate_rag_answer` 线性 RAG。

### 4.4 与技能包

- `skill.tool_names`：引用 **builtin / custom** 的 slug
- MCP：通过智能体 `mcp_service_ids` 绑定；技能包可不重复列举 MCP tool 名（或未来支持 `mcp:` 前缀引用）

---

## 5. 管理面 vs 运行面

| 维度 | 管理面（工作台） | 运行面（Agent） |
|------|------------------|-----------------|
| **内置工具** | 工具列表只读展示 | 可 call |
| **HTTP / 脚本** | `/workbench/tools` CRUD | 可 call |
| **MCP** | `/workbench/mcp` 注册与同步 | 绑定 `mcp_service_ids` 后可 call |
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

### P1 — 提升自定义与 RAG 协同

| 项 | 说明 |
|----|------|
| 脚本预注入 stdlib | ✅ 已实现：Runner 注入 `json`、`datetime`、`re`、`math`；仍禁用户 `import` |
| 内置复杂工具（首批） | ✅ `compliance_check_text` 已实现；`knowledge_search` 已增强为多库 + 回填 `sources`；`list_knowledge_bases` 决定**不做**（prompt 已注入 `kb_ids`） |
| 工具分组/标签 | 工作台区分 L1/L2 内置 |

### P2 — 平台厚度

| 项 | 说明 |
|----|------|
| 内置复杂工具（扩展） | ✅ `run_flow_once`、`invoke_tenant_hook` 已实现；附件类需先补「会话/资源范围」语义 |
| 租户套餐级 builtin 开关 | `tenant_toggle` / 套餐位 |
| 调用限流 | 租户级 QPS / 复杂工具配额 |
| 流程节点 | 复用同一 Runtime |

### 明确不做（短期）

- 租户在 UI 内编写任意 import 的 Python 工程
- 平台内置 bash / 通用文件系统工具（与 MCP/AIO Sandbox 产品线区分）

---

## 8. 已实现与代码入口

已实现：builtin/custom catalog、变换脚本 v2（预注入 `json`/`re`/`math`/`datetime`）、`tool_agent`、
MCP 工作台、**RAG 与 tool calling 共存**（绑定 KB 时 `knowledge_search` 由 LLM 自行调用，命中回填 `sources`）、
**L2 内置 `compliance_check_text`**（复用租户词库，只读不写审计）、
**L2 内置 `run_flow_once`**（仅已发布流程 + 确认 + 递归/超时护栏）、
**L2 内置 `invoke_tenant_hook`**（仅 HTTP 钩子 + 确认 + 手动触发结果回传），
**opt-in 内置工具机制**（`tool_slugs` 显式勾选才注入，基线与 opt-in 分离），以及
**MCP → Agent function calling**（`mcp__{service}__{tool}`，审计 `source=mcp`）；见 [guides/tools.md](../guides/tools.md)。
未尽项见 §7 演进路线。

代码入口：

| 模块 | 路径 |
|------|------|
| 工具 Service / API | `backend/packages/miles-portal/src/miles_portal/tenant/tools/` |
| 执行 | `tenant/tools/invoke.py` |
| 内置复杂工具 | `tenant/tools/services/flow_once.py`、`tenant/tools/services/hook_once.py` |
| LangChain 加载 | `integrations/langchain/toolkit/catalog.py`、`tool_agent.py` |
| 平台 Hook 执行 | `backend/packages/miles-portal/src/miles_portal/tenant/hooks/services/executor/` |
| MCP | `backend/packages/miles-portal/src/miles_portal/tenant/mcp/` |
| Runner | `backend/packages/miles-runner/src/miles_runner/`（MCP runner 进程）、`backend/packages/miles-exec/src/miles_exec/sandbox/`（工具沙箱） |

---

## 9. 相关文档

- [工具指南（API 与现网行为）](../guides/tools.md)
- [MCP 服务指南](../guides/mcp.md)
- [MCP Runner 沙箱](./mcp-sandbox.md)
