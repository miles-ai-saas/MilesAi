# LangChain 工具 schema 模块拆分与声明式收敛

- 状态：设计待评审
- 日期：2026-09-16
- 前序：2026-09-13 后端代码规范评审「第 3 批 · 结构性重构」项 8（该评审未落为 spec 文件；原文记为
  「拆 `tools.py`（617 行）→ 归并 15 个重复工厂」；实测为 **13 个静态工厂 + 3 个 spec 驱动工厂**，见 §2）

## 1. 问题

`miles_ai/integrations/langchain/tools.py` 一个文件承担 **6 类互不相干**的职责，且其中 13 个
工厂函数是**同一段代码抄 13 遍**：

1. MCP function name 的命名约定（`sanitize_ident` / `compose_mcp_tool_name` / `is_mcp_tool_name`）；
2. 租户工具 / MCP 工具的中性 spec（`CustomToolSpec` / `McpToolSpec`）；
3. JSON Schema → pydantic 的转换器（`json_schema_to_pydantic` 及其 3 个内部辅助）；
4. 13 个入参 DTO（纯声明，13 个 `class XxxInput(BaseModel)`）；
5. 13 个内置工具的 schema 工厂；
6. 总装配 `build_platform_tools`。

后果有三，都不是「行数不好看」而已：

- **改一处要抄 13 遍。** 13 个工厂的函数体是同一个形状——定义占位 `_run`/`_arun`（体为
  `raise RuntimeError("请通过 invoke_tool_with_context 执行 <slug>")`）再 `StructuredTool.from_function(...)`。
  这条「占位必须报错、执行一律走 L1」是本模块**唯一的实质不变量**，却重复了 13 份：
  任何一处漏写报错体，该工具就会变成「看起来能执行、实际静默返回 None」的陷阱，而现有测试测不到。
- **新增工具要动 3 处。** 加一个内置工具需要：写工厂函数、加进对应的 `get_*` 列表、
  （opt-in 类）再登记进 `_OPT_IN_BUILTIN_MAKERS` 字典。
- **职责混杂使「谁能依赖谁」无法表达。** `naming`（纯字符串约定，被 4 处生产代码引用）与
  `inputs`（纯 DTO）本可被单独引用，现在只能整包引入，import 段把 6 类依赖焊在一起。

## 2. 现状（实测）

`tools.py` 共 **617 行**，分区如下：

| 区块 | 行 | 内容 | 外部引用 |
|---|---|---|---|
| MCP 命名 | 43–98 | `MCP_FUNCTION_PREFIX`、`sanitize_ident`、`_service_ident`、`compose_mcp_tool_name`、`is_mcp_tool_name`、`select_agent_tools` | `naming` 部分被 4 处生产代码引用 |
| 中性 spec | 100–121 | `CustomToolSpec`、`McpToolSpec` | 被 portal 的 L1 loader 引用 |
| JSON Schema→pydantic | 123–188 | `_field_name`、`mcp_param_alias`、`json_schema_to_pydantic`、`_json_scalar_type` | 被测试引用 |
| 入参 DTO | 189–297 | 13 个 `BaseModel` | 无（仅本模块内被 `args_schema=` 引用） |
| **工厂** | **299–590** | **13 个静态工厂** + 3 个 spec 驱动工厂（`make_custom_http_tool`、`make_custom_script_tool`、`make_mcp_tool`） | 仅 `make_knowledge_search_tool` 被 1 处测试引用 |
| 总装配 | 593–617 | `build_platform_tools` | 生产 1 处 + 测试 4 处 |

工具分组（共 13 个静态工具）：

| 分组 | slug | 工厂入参形态 |
|---|---|---|
| 平台（恒在） | `calculator`、`http_request`、`get_current_datetime`、`knowledge_search` | **同步** `func` |
| opt-in（须勾选） | `web_search`、`code_execution`、`compliance_check_text`、`run_flow_once`、`invoke_tenant_hook` | 异步 `coroutine`（经 `_opt_in_marker`） |
| 技能（绑定技能包） | `skill_read_reference`、`skill_run_script` | 异步 |
| 生成（开关开启） | `generate_image`、`generate_video` | 异步 |

**同步 / 异步不是风格差异，而是必须保留的形状**：4 个平台工具用 `func=`（同步），其余 9 个用
`coroutine=`。`StructuredTool` 据此决定 `.func` / `.coroutine` 哪个非空。

**占位报错文案是统一的**：13 个静态工具 + 3 个 spec 驱动工具的报错体均为
`请通过 invoke_tool_with_context 执行 {slug}`（`slug` 即工具名），无例外。

调用面共 **11 处**（生产 7 + 测试 4），最集中的一处只需 4 个符号：

| 侧 | 文件 | 符号数 |
|---|---|---|
| 生产 | `miles_portal/tenant/tools/services/mcp_tools.py:22` | 4 |
| 生产 | `miles_portal/tenant/tools/services/custom_tools.py:14` | 2 |
| 生产 | `miles_portal/tenant/tools/services/tools.py:21` | 1 |
| 生产 | `miles_portal/tenant/tools/confirmation.py:8` | 1 |
| 生产 | `miles_portal/tenant/tools/invoke/context.py:12` | 1 |
| 生产 | `miles_portal/tenant/agents/services/context.py:15` | 1 |
| 生产 | `miles_ai/integrations/langchain/tool_agent/loop.py:19` | 2 |
| 测试 | `tests/mcp/test_mcp_function_calling.py:11` | 8 |
| 测试 | `tests/tenant/tools/test_builtin_opt_in.py:5` | 3 |
| 测试 | `tests/tenant/tools/test_knowledge_search_coexistence.py:13` | 3 |
| 测试 | `tests/tenant/skills/test_skill_runtime_integration.py:7` | 模块引用 |

**无任何代码依赖私有名**（13 个 `_make_*`、`_opt_in_marker`、`_OPT_IN_BUILTIN_MAKERS`、
`_json_scalar_type`、`_field_name`、`_service_ident` 在 `tools.py` 之外零引用），故内部形态可自由重塑。

## 3. 目标

1. 按职责拆为 `toolkit/` 子包 4 模块，每模块单一职责，均 <200 行。
2. 13 个静态工厂收敛为**声明表 + 单一构造器**；新增内置工具 = 加一行数据。
3. 占位报错文案与同步 / 异步分支**各只存一处**。
4. 消除调用点对「一个 617 行模块」的整体依赖：按职责 import（`naming` / `inputs` / `specs` / `catalog`）。

## 4. 非目标

- **不改任何对外可观测行为**：工具名、description、`args_schema`、报错文案、装配顺序、
  门控逻辑（`tool_slugs` 白名单、`skill_package_id`、`enable_generative_tools`）逐字节不变。
- 不改 `CustomToolSpec` / `McpToolSpec` 的字段（portal 的 L1 loader 依赖其形状）。
- 不碰 `miles_portal/tenant/tools/`——那是租户域的 tools CRUD 与执行分发，与本文的
  「工具 schema 构造」是两件事，`toolkit` 命名不与之共享语义。
- 不引入新依赖；不改 import-linter 契约（契约按包分层，包内拆子包不影响）。
- 不动 13 个 DTO 的字段与 description（LLM 可见，属对外行为）。

## 5. 方案

### 5.1 目录与模块划分

```
miles_ai/integrations/langchain/
├── toolkit/
│   ├── __init__.py   # 空 —— 刻意不构成再导出壳
│   ├── naming.py     # MCP function name 约定
│   ├── inputs.py     # 13 个入参 DTO（纯声明目录）
│   ├── specs.py      # 中性 spec + JSON Schema → pydantic
│   └── catalog.py    # 声明表 + 构造器 + 分组 + 选型 + 总装配
└── tools.py          # 删除
```

依赖方向**单向无环**：`catalog → {inputs, specs, naming}`；`inputs` / `specs` / `naming` 三者互不依赖。
这正是当前「一个 import 段把所有职责焊在一起」无法表达的性质。

`tool_agent/` 已是同级子包先例（`loop.py` / `parse.py` / `tool_contract.py`），目录形态与之一致。

### 5.2 声明式注册表

```python
@dataclass(frozen=True)
class ToolDecl:
    slug: str
    description: str
    args_schema: type[BaseModel]
    is_async: bool = True   # 4 个平台工具为 False（现状即同步 func）
```

13 条声明按 §2 的四组排列，由**唯一**构造器产出：

```python
def build_stub_tool(
    slug: str,
    description: str,
    args_schema: type[BaseModel] | None,
    *,
    is_async: bool,
) -> StructuredTool:
    """占位壳：name/description/args_schema 供 LLM 选型，执行一律走 L1 invoke_tool_with_context。"""
```

构造器内部承担三件**原先抄了 13 遍**的事：占位函数体（报错文案 `请通过 invoke_tool_with_context 执行 {slug}`）、
`func` / `coroutine` 二选一、`args_schema` 传递（`None` 时不传该 kwarg）。

3 个 spec 驱动工厂（`make_custom_http_tool` / `make_custom_script_tool` / `make_mcp_tool`）入参来自
运行时 spec 而非模块常量，故**不入表**，但共用同一构造器——这是重复消除的另一半。
`make_mcp_tool` 的「`json_schema_to_pydantic` 返回 `None` 时不传 `args_schema`」情形由构造器的
`args_schema=None` 分支承接（现状行为不变）。

分组用常量声明而非散落的列表：

```python
_PLATFORM_SLUGS   = ("calculator", "http_request", "get_current_datetime", "knowledge_search")
_OPT_IN_SLUGS     = ("web_search", "code_execution", "compliance_check_text", "run_flow_once", "invoke_tenant_hook")
_SKILL_SLUGS      = ("skill_read_reference", "skill_run_script")
_GENERATIVE_SLUGS = ("generate_image", "generate_video")
```

`get_platform_tools()` / `select_opt_in_builtin_tools(cfg)` / `get_skill_bound_tools()` /
`get_generative_tools()` 退化为对表的薄视图，**顺序与现状逐一对齐**（由既有测试盯住，见 §7）。
另以 `make_builtin_tool(slug)` 取代现有的单个工具获取入口（`make_knowledge_search_tool()`）：
实现为声明表查找，**未知 slug 抛 `KeyError`**（现状无「未知工具返回 `None`」语义，不新增该语义）。

### 5.3 数据流（改造后）

```
build_platform_tools(cfg, custom_specs, mcp_specs)
  ├─ get_platform_tools()               ← _PLATFORM_SLUGS   → _DECLS[slug] → build_stub_tool
  ├─ select_opt_in_builtin_tools(cfg)   ← cfg["tool_slugs"] ∩ _OPT_IN_SLUGS
  ├─ get_skill_bound_tools()            ← cfg["skill_package_id"] 存在时
  ├─ get_generative_tools()             ← cfg["enable_generative_tools"] 为真时
  ├─ make_custom_{http,script}_tool(spec)  ← spec.tool_type 分派
  └─ make_mcp_tool(spec)
```

与现状**逐节点相同**，只是「工厂函数」全部变成「查表 + 构造器」。

### 5.4 调用点迁移（11 处，不保留转发壳）

| 文件 | 迁移后 import |
|---|---|
| `tools/services/mcp_tools.py:22` | `specs`（`McpToolSpec`、`mcp_param_alias`）+ `naming`（`compose_mcp_tool_name`、`is_mcp_tool_name`） |
| `tools/services/custom_tools.py:14` | `specs.CustomToolSpec` + `catalog.build_platform_tools` |
| `tools/services/tools.py:21` | `naming.is_mcp_tool_name` |
| `tools/confirmation.py:8` | `naming.is_mcp_tool_name` |
| `tools/invoke/context.py:12` | `naming.is_mcp_tool_name` |
| `agents/services/context.py:15` | `naming.compose_mcp_tool_name` |
| `langchain/tool_agent/loop.py:19` | `catalog.get_skill_bound_tools` + `naming.select_agent_tools` |
| `tests/mcp/test_mcp_function_calling.py:11` | `naming`（4）+ `specs`（3）+ `catalog.build_platform_tools` |
| `tests/tenant/tools/test_builtin_opt_in.py:5` | `catalog`（3） |
| `tests/tenant/tools/test_knowledge_search_coexistence.py:13` | `naming.select_agent_tools` + `catalog`（`get_platform_tools`、`make_builtin_tool("knowledge_search")`） |
| `tests/tenant/skills/test_skill_runtime_integration.py:7` | `from ...toolkit import catalog` |

`select_agent_tools` 归 `naming.py`（它只做「按 name 过滤」，与 MCP 命名规则同属名称语义）；
`catalog.py` 反向依赖它，方向仍是 `catalog → naming`。

**为什么不留转发壳**：上一专项（loop 感知 DB 引擎）已确立同一结论——转发壳会保留两条
「同一件事的入口」，而漏改调用点的失败模式是**导入期 `ImportError`**（响亮、即时、无法忽略），
不是静默降级。这也是不留壳的前提条件，`rg "langchain\.tools"` 归零即收口判据。

## 6. 语义变化

**无。** 本设计是纯结构重构：不新增 / 不删除任何工具，不改任何 description 与 schema，
不改门控判定。唯一的变化是**符号所在模块**。

唯一需要留意的形似变化：`make_knowledge_search_tool()` → `catalog.make_builtin_tool("knowledge_search")`。
前者是公开名（被 1 处测试引用），属调用点迁移的一部分，非行为变化。

## 7. 测试策略

**顺序是「先冻结，再重构」。**

### 7.1 重构前：特征测试冻结对外可观测面

新增 `tests/tenant/tools/test_toolkit_contract.py`，在重构**之前**写下并跑绿，覆盖：

1. **13 个静态工具的 `name` / `description` / `args_schema` JSON**：期望值**内联**在测试文件内
   （由当前实现跑出后粘贴并人工审阅），不引入需维护的 fixture 文件。
   这一条是「声明表抄错一个字符」这类**最难靠人眼发现**的错误唯一的拦截手段——13 条 description 中
   有 **7 条超过 100 字符**（最长 199 字符，如 `generate_image` 的「…禁止四宫格或分镜拼贴」、
   `generate_video` 的「耗时长，异步排队」），逐字搬运极易出错。
2. **3 个 spec 驱动工具的 schema**：各给一个样例 spec（custom-http / custom-script / mcp），
   含 `make_mcp_tool` 在 `input_schema=None` 与可解析两种情形。
3. **占位报错文案**：对代表各分组（平台/opt-in/技能/生成 + spec 驱动）的工具调用 `invoke` / `ainvoke`，
   断言 `RuntimeError` 且文案为 `请通过 invoke_tool_with_context 执行 <slug>`。
   **现状无用例覆盖这条不变量**，是本设计补上的第一个缺口。
4. **同步 / 异步形状**：4 个平台工具断言 `tool.func is not None` 且 `tool.coroutine is None`；
   其余断言反向。这是单构造器若一律传 `coroutine=` 时**唯一会响**的用例（见 §8 R1）。
5. **门控组合**：`build_platform_tools` 在「仅 `skill_package_id`」「仅 `enable_generative_tools`」
   「都给」「都不给」四种组合下的工具名集合。现状仅覆盖技能那一半。

### 7.2 重构后

- 上述特征测试**必须原样全绿**（不改期望值、不迁就实现）。
- 既有 4 个测试文件仅改导入路径（与 §5.4 一一对应）。
- 增量断言：`rg "langchain\.tools"` 在 `packages/` 与 `tests/` 归零。
- 五道门禁：`ruff format --check`、`ruff check`、`lint-imports`（6 契约）、`export_openapi --check`、
  `python -m pytest`（全量）。OpenAPI 快照尤其关键——13 个 DTO 的 description 会进 function schema，
  若被改动，快照会响。

预期计数：基线 **1079** → 新增 1 个测试文件（约 5–8 条用例）。实际数以实测为准并记录，
**不为了对齐估计值而增删用例**。

## 8. 风险

| # | 风险 | 对策 |
|---|---|---|
| R1 | 单构造器误把 4 个同步平台工具变异步（`StructuredTool` 会静默接受） | `ToolDecl.is_async` + §7.1.4 的方向性断言 |
| R2 | 抄错 description / schema 绑定 | §7.1.1 的全量冻结测试，**重构前先绿** |
| R3 | 漏写某个工具的占位报错体（原本抄 13 遍） | 结构上不可能：报错体只存于构造器一处 |
| R4 | 漏改调用点 | 导入期 `ImportError`；且 `rg "langchain\.tools"` 归零作为收口判据 |
| R5 | 文档 / docstring 里的旧路径 | 已定位 `miles_core/models/tool/__init__.py:4` 的 docstring 提到 `integrations.langchain.tools`，随改动同步 |
| R6 | 子包内出现环 | `catalog → {inputs, specs, naming}` 单向；`lint-imports` 6 契约须仍全绿 |
| R7 | 与 `miles_portal/tenant/tools/` 语义混淆 | 已在 §4 界定：前者是 schema 构造，后者是租户域 CRUD / 执行分发 |

## 9. 遗留

- MCP 命名规则 `compose_mcp_tool_name` 的 64 字符截断 + 短哈希碰撞，当前靠「4 位十六进制」，
  理论上存在碰撞（服务名极多时）。不在本次范围，此处仅登记。
- `select_agent_tools` 的 `always_allow` 机制是「调用方记得传」，属与 loop 感知 DB 专项
  §1.2 同类形状（正确性依赖调用点）。不在本次范围。
- 本次不动 `miles_portal/tenant/tools/` 下的同名概念（该目录 `services/tools.py` 365 行、
  `views/tools.py` 128 行），如需治理另立专项。

## 10. 修订记录

- 2026-09-16 初始设计。基于只读勘察：`tools.py` 617 行的 6 区实测行号、11 处调用面、
  「无外部代码依赖私有名」的核实结论；并以探针实测验证「显式 `args_schema` + `**kwargs` 占位」
  与现状「带类型签名的占位」产出的 `name` / `description` / `args_schema` / `args` /
  `tool_call_schema` 及报错文案**逐字节相同**，故 §5.2 的收敛不改变对外行为。
  同时更正前序评审的一处估计：可归并的工厂为 **13 个静态 + 3 个 spec 驱动**，非「15 个」。
