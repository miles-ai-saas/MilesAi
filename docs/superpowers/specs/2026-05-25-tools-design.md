# 工具功能 v1 设计规格

> **归档：** 立项过程稿（2026-05-25）。**现网规格：** [features/tools-mcp-skills.md](../../features/tools-mcp-skills.md) · [architecture/tools-runtime.md](../../architecture/tools-runtime.md)

**日期：** 2026-05-25  
**状态：** 归档（v1 已落地；v2 脚本/沙箱见 tools-runtime §8）

---

## 1. 背景与目标

MilesAI 已有基础工具模块（内置 `calculator` / `http_request` / `knowledge_search`、自定义 HTTP 工具、MCP 同步目录），但前端为简陋双 Tab，缺少分类、参数 schema、统一卡片 UI。

v1 目标：对齐参考 UI，交付可用的 HTTP 自定义工具管理，并为 v2 脚本工具预留扩展点。

### 1.1 v1 交付范围

- 统一工具工作台 UI（全部 / 内置 / 自定义 Tab + 分类筛选）
- 内置工具注册表（含参数 schema、新增 `get_current_datetime`）
- 自定义 HTTP 工具 CRUD：slug、分类、版本、参数 schema、试调用
- catalog API 合并 builtin + custom（**不含 MCP**，见 [tools.md](../../guides/tools.md) §6）
- Agent LangChain 动态 StructuredTool（自定义 HTTP）

### 1.2 v1 不做

- 在线 Python/Java 脚本编辑器与沙箱执行
- 调用频率限制、审计日志表
- PRD 中全部内置工具（OCR、Redis 等）
- MCP 在工具页的 CRUD（仍跳转 MCP 页）
- `require_confirmation` 在 Agent 循环中生效（v1.5）

### 1.3 v2 预留

- `tool_type = script`（v1 禁止创建）
- UI 顶部 banner 提示脚本工具即将上线
- 执行复用 MCP Runner 沙箱架构（`docs/architecture/mcp-sandbox.md`）

---

## 2. 数据模型

### 2.1 `tool_tools` 表扩展

| 字段 | 类型 | 说明 |
|------|------|------|
| `slug` | VARCHAR(64) NOT NULL | 工具编号，租户内唯一，`snake_case` |
| `name` | VARCHAR(128) | 显示名称（保留现有列） |
| `description` | TEXT | 描述 |
| `tool_type` | enum | `http`（v1）；`script`（预留，v1 禁创建） |
| `category_id` | UUID NULL | → `sys_categories`，domain=`tool` |
| `version` | VARCHAR(16) | 默认 `1.0.0` |
| `require_confirmation` | BOOLEAN | 默认 `false`（v1 仅存储） |
| `parameters` | JSONB | 输入参数 schema 数组 |
| `config` | JSONB | HTTP 专有配置 |
| `is_active` | BOOLEAN | 启用/禁用 |

约束：`UNIQUE(tenant_id, slug)`；迁移时对现有行从 `name` 回填 slug。

移除 enum 值 `builtin`（内置工具不入库，由代码注册表维护）。

### 2.2 `parameters` 格式

JSON 数组，JSON Schema 子集，兼容 OpenAI function calling：

```json
[
  {
    "name": "city",
    "type": "string",
    "description": "城市名称",
    "required": true
  },
  {
    "name": "unit",
    "type": "string",
    "enum": ["celsius", "fahrenheit"],
    "required": false,
    "default": "celsius"
  }
]
```

支持类型：`string` | `number` | `integer` | `boolean`。参数名不可重复。

### 2.3 HTTP `config` 结构

```json
{
  "url": "https://api.example.com/weather?city={{city}}",
  "method": "GET",
  "headers": { "Authorization": "Bearer xxx" },
  "body_mode": "json",
  "timeout_sec": 15,
  "response_path": "data.result"
}
```

- `body_mode`：`json`（默认）| `none`
- URL / headers 支持 `{{param_name}}` 模板替换
- `response_path`：可选，点分路径提取 JSON 字段（v1 简单实现）

### 2.4 分类

扩展 `CategoryDomain`：`TOOL = "tool"`。

默认 seed 分类：

| name | slug | sort_order |
|------|------|------------|
| 未分类 | uncategorized | 0 |
| 通用 | general | 10 |
| 集成 | integration | 20 |
| 数据 | data | 30 |

---

## 3. 内置工具注册表

代码维护 `BUILTIN_REGISTRY`（替代现有 `BUILTIN_TOOLS` 列表），结构：

```python
{
  "slug": "get_current_datetime",
  "name": "获取当前时间",
  "description": "获取当前的日期时间",
  "category_slug": "general",
  "version": "1.0.0",
  "require_confirmation": False,
  "parameters": [
    {"name": "timezone", "type": "string", "description": "IANA 时区", "required": False}
  ],
}
```

v1 内置工具清单：

| slug | name |
|------|------|
| calculator | 计算器 |
| http_request | HTTP 请求 |
| knowledge_search | 知识库检索 |
| get_current_datetime | 获取当前时间（新增） |

---

## 4. API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/tools/catalog?source=&category_id=` | 统一目录 |
| GET | `/tools?category_id=` | 自定义工具分页 |
| POST | `/tools` | 创建 HTTP 工具 |
| PATCH | `/tools/{id}` | 更新 |
| DELETE | `/tools/{id}` | 软删除 |
| POST | `/tools/{slug}/invoke` | 试调用 |
| GET | `/tools/builtin` | 内置详情 |

### 4.1 校验规则

- `slug`：`^[a-z][a-z0-9_]{0,62}$`，租户内唯一，不可与内置 slug 冲突
- HTTP 工具 `config.url` 必填
- URL SSRF 校验：复用 `validate_mcp_endpoint_url`（提取为共用 `validate_outbound_url`）
- `tool_type=script` 创建时返回 400

### 4.2 `ToolCatalogItem` 扩展字段

`slug`, `category_id`, `category_name`, `parameters`, `version`, `require_confirmation`, `updated_at`

---

## 5. 执行链路

```
Agent / 流程 / 试调用
    → invoke_tool_by_name(slug, params, tool_id?)
        → 内置：invoke_builtin（registry 分发）
        → 自定义 HTTP：validate_params → template URL → httpx → 截断 4KB
```

### 5.1 HTTP 执行升级

1. 按 `parameters` 校验入参（必填、类型、enum）
2. GET：params → query string；POST/PUT：params → JSON body
3. 模板替换 URL / headers 中的 `{{param}}`
4. 响应可选 `response_path` 提取

### 5.2 Agent 集成

`integrations/langchain/tools.py` 新增：

- `parameters_to_pydantic(parameters) -> type[BaseModel]`
- `make_custom_http_tool(tool: Tool) -> StructuredTool`
- Agent 运行时加载租户 `is_active=True` 的 HTTP 工具

---

## 6. 前端 UI

路径：`/workbench/tools`

### 6.1 布局

- Tab：**全部** / **内置** / **自定义**
- 分类 Tab：复用 `useCategoryTabs("tool")` + `CategoryManageDialog`
- 网格：`AddResourceCard` + `ToolCard`（参考 `McpServiceCard`）
- 搜索：name / slug / description

### 6.2 组件

| 组件 | 职责 |
|------|------|
| `ToolCard` | 卡片：图标、slug、描述、来源/分类 badge、时间、··· 菜单 |
| `ToolCreateDialog` | 创建/编辑 HTTP 工具表单 |
| `ToolParameterEditor` | 动态参数列表 |
| `ToolTestDialog` | 按 parameters 生成试调用表单 |

### 6.3 v1 表单字段

标签（分类）、名称、编号（slug）、描述、是否需要确认（toggle）、版本号、输入参数、HTTP 配置（URL / Method / Headers）。

顶部 info banner：

> 当前支持 HTTP 工具。脚本工具（在线代码）将在后续版本提供；异步/流式工具请通过 MCP 接入。

**v1 不包含代码编辑器。**

### 6.4 Tab 行为

| Tab | 内容 | 操作 |
|-----|------|------|
| 全部 | builtin + custom | 试调用 |
| 内置 | 仅 builtin | 只读 + 试调用 |
| 自定义 | custom HTTP | CRUD + 试调用 |

MCP 工具在 MCP 工作台（`/workbench/mcp`）管理，不在工具页展示。

---

## 7. 关联模块

| 模块 | 变更 |
|------|------|
| 技能包 `tool_names` | 继续存 slug |
| Agent `context.py` | 展示 parameters 摘要 |
| MCP | 无变更；**不在**工具 catalog 合并，见 [tools.md](../../guides/tools.md) |
| 租户删除 | 已有 Tool 硬删，无需改 |
| 前端 `CategoryDomain` | 增加 `"tool"` |

---

## 8. Migration

表结构由 ORM 定义；唯一迁移文件 `alembic/versions/001_initial_schema.py`（`Base.metadata.create_all`）。

```bash
cd backend && alembic upgrade head
```

旧库若曾使用 002–012 增量 revision 且表结构已与当前 ORM 一致：`alembic stamp 001`。

---

## 9. 测试

| 场景 | 文件 |
|------|------|
| slug 校验与唯一性 | `test_tools_schema.py` |
| parameters 校验 | `test_tools_schema.py` |
| HTTP 执行 GET/POST | `test_tools_invoke.py` |
| SSRF URL 拦截 | `test_tools_invoke.py` |
| get_current_datetime | `test_tools_invoke.py` |
| catalog 合并 | `test_tools_service.py` |

---

## 10. 路线图

| 阶段 | 内容 |
|------|------|
| **v1** | 本规格 |
| **v1.5** | 调用日志；`require_confirmation` Agent 循环 |
| **v2** | `script` 类型 + 沙箱 + 代码编辑器 |
