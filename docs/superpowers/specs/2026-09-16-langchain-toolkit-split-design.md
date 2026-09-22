# LangChain 工具 schema 模块拆分与声明式收敛

- 状态：设计待评审
- 日期：2026-09-16
- 前序：2026-09-13 后端代码规范评审「第 3 批 · 结构性重构」项 8（该评审未落为 spec 文件；原文记为
  「拆 `tools.py`（617 行）→ 归并 15 个重复工厂」；实测为 **13 个静态工厂 + 3 个 spec 驱动工厂**，见 §2）

## 1. 问题

`miles_integrations/langchain/tools.py` 一个文件承担 **6 类互不相干**的职责，且其中 13 个
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
| MCP 命名 | 43–98 | `MCP_FUNCTION_PREFIX`、`sanitize_ident`、`service_ident`、`ident_collision`、`compose_mcp_tool_name`、`is_mcp_tool_name`、`select_agent_tools` | `naming` 部分被 4 处生产代码引用 |
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
| 生产 | `miles_integrations/langchain/tool_agent/loop.py:19` | 2 |
| 测试 | `tests/mcp/test_mcp_function_calling.py:11` | 8 |
| 测试 | `tests/tenant/tools/test_builtin_opt_in.py:5` | 3 |
| 测试 | `tests/tenant/tools/test_knowledge_search_coexistence.py:13` | 3 |
| 测试 | `tests/tenant/skills/test_skill_runtime_integration.py:7` | 模块引用 |

**无任何代码依赖私有名**（13 个 `_make_*`、`_opt_in_marker`、`_OPT_IN_BUILTIN_MAKERS`、
`_json_scalar_type`、`_field_name`、`_service_ident` 在 `tools.py` 之外零引用），故内部形态可自由重塑。

## 3. 目标

1. 按职责拆为 `toolkit/` 子包 4 模块，每模块单一职责，均 <200 行。
   > **实施修订**：`catalog.py` 实测 **226 行**（非空行 177，其中 49 空行 + 4 注释行），
   > 超出本目标 26 行；其余三模块为 `inputs.py` 118 / `specs.py` 103 / `naming.py` 72。
   > 超出来源是 `_DECLS` 声明块（13 条 description 最长 77 字符，必须**逐字**内联）
   > 与模块 docstring；「单一职责」仍成立。此处保留原目标数值以便对照，偏差记入 §10。
2. 13 个静态工厂收敛为**声明表 + 单一构造器**；新增内置工具 = 加一行数据。
3. 占位报错文案与同步 / 异步分支**各只存一处**。
4. 消除调用点对「一个 617 行模块」的整体依赖：按职责 import（`naming` / `inputs` / `specs` / `catalog`）。

## 4. 非目标

- **不改任何对外可观测行为**：工具名、description、`args_schema`、报错文案、装配顺序、
  门控逻辑（`tool_slugs` 白名单、`skill_package_id`、`enable_generative_tools`）逐字节不变。
- 不改 `CustomToolSpec` / `McpToolSpec` 的字段（portal 的 L1 loader 依赖其形状）。
- 不改 `miles_portal/tenant/tools/` 的**业务语义**——那是租户域的 tools CRUD 与执行分发，
  与本文的「工具 schema 构造」是两件事，`toolkit` 命名不与之共享语义。
  本分支确实会触及该目录下 5 个文件（`confirmation.py`、`invoke/context.py`、
  `services/custom_tools.py`、`services/mcp_tools.py`、`services/tools.py`），但**仅限**
  import 语句指向 `toolkit/*` 与 docstring/注释里的路径文案，**不得有任何语句级逻辑变化**
  （函数体、条件、参数、返回值）——该判据由 Task 4 Step 4 逐文件通读 diff 核验。
- 不引入新依赖；不改 import-linter 契约（契约按包分层，包内拆子包不影响）。
- 不动 13 个 DTO 的字段与 description（LLM 可见，属对外行为）。

## 5. 方案

### 5.1 目录与模块划分

```
miles_integrations/langchain/
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
    description: str
    args_schema: type[BaseModel]
    is_async: bool = True   # 4 个平台工具为 False（现状即同步 func）
```

> **实施修订**：`ToolDecl` **不设** `slug` 字段，slug 由声明表的键承载
> （`_DECLS: dict[str, ToolDecl]`），省去 13 次重复书写。行为无差异，详见 §10。

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
不是静默降级。这也是不留壳的前提条件，`rg "langchain[./]tools|langchain import tools"` 归零即收口判据
（**只查点号形式不足**，理由见 §7.2）。

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
   这一条是「声明表抄错一个字符」这类**最难靠人眼发现**的错误唯一的拦截手段——13 条 description
   全部是中文，最长 **77 字符**（177 UTF-8 字节，如 `generate_video` 的「耗时长，异步排队」），
   最长一条冻结的 schema 字面量达 **889 字符**，逐字搬运极易出错。
   （**勘误 10（终审实测修正）**：原文写「7 条超过 100 字符（最长 199）」——该数字在任何度量下
   都不成立，实测字符 9–77（0 条超 100）、UTF-8 字节 18–177、转义 ASCII 30–327。详见 §10。）
2. **spec 驱动工具的 schema**：各给一个样例 spec（custom-http / custom-script / mcp 可解析 /
    mcp `input_schema=None` **共 4 类**），断言 description / 同步异步形状 / schema JSON 不变。
    第 4 类（`input_schema=None`）是独立风险点：此时整个 `args_schema` kwarg 被省略，
    LangChain 从占位签名反推 schema、`title` 取工具名，故占位签名不得改动。
3. **占位报错文案**：对代表各分组（平台/opt-in/技能/生成 + spec 驱动）的工具**直接调用占位函数本体**
   （`tool.func()` / `asyncio.run(tool.coroutine())`），断言 `RuntimeError` 且文案为
   `请通过 invoke_tool_with_context 执行 <slug>`。
   **现状无用例覆盖这条不变量**，是本设计补上的第一个缺口。
   注意**不能**用 `tool.invoke({})`：那会先过 pydantic 校验，空参先抛 `ValidationError`
   （实测 `calculator.invoke({})` → `ValidationError: Field required`），测不到占位体；
   占位统一为 `**kwargs`，`_call_stub` 据此按签名适配（详见 §10）。
4. **同步 / 异步形状**：4 个平台工具断言 `tool.func is not None` 且 `tool.coroutine is None`；
   其余断言反向。这是单构造器若一律传 `coroutine=` 时**唯一会响**的用例（见 §8 R1）。
5. **门控组合**：`build_platform_tools` 在「仅 `skill_package_id`」「仅 `enable_generative_tools`」
   「都给」「都不给」四种组合下的工具名**精确有序列表**（非集合——装配顺序 platform → opt-in →
   skill → generative → custom → mcp 本身是对外行为，集合语义既看不出顺序，也发现不了重复工具）。
   现状仅覆盖技能那一半。
6. **声明表与分组双向一一对应（不变量类断言）**：`test_decl_registry_and_groups_are_in_bijection`
   断言 `_DECLS` 的键集与四个分组元组（`_PLATFORM_SLUGS` / `_OPT_IN_SLUGS` / `_SKILL_SLUGS` /
   `_GENERATIVE_SLUGS`）的并集**完全相等**，且任一 slug 不得同时归入两个分组。

> 上述 1–5 条冻结的是**输出**（description、schema JSON、报错文案、同步异步形状、装配顺序与
> 门控结果）；第 6 条是**不变量**断言，性质不同，故单列。理由：`_DECLS` 只在
> `_DECLS[slug]` 处被查表、**从不被遍历**，一个工具的可见性完全取决于它是否落在某个分组元组里。
> 于是故障是不对称的——**只加声明不加分组 → 工具静默缺席且不报错**（任何工具列表都取不到，
> 调用方看不出异常）；只加分组不加声明 → 构造时才 `KeyError`（响亮）。1–5 条都抓不到前者：
> 参数化来自本文件内联的 `_EXPECTED_BUILTIN`，新增声明不会被它覆盖。而
> `docs/guides/ai-stack.md` 正是教贡献者新增内置工具的**可执行指南**，走的恰是「加声明」这条路径，
> 故必须在此钉住。该用例来自复评 m1，属 §7.1 清单之外补入的护栏（见 §10）。

### 7.2 重构后

- 上述特征测试**必须原样全绿**（不改期望值、不迁就实现）。
- 既有 4 个测试文件仅改导入路径（与 §5.4 一一对应），**除** `test_knowledge_search_coexistence.py`
  另有一处函数改名（`test_make_knowledge_search_tool_schema_allows_kb_ids` →
  `test_knowledge_search_tool_schema_allows_kb_ids`）与调用改写
  （`make_knowledge_search_tool()` → `make_builtin_tool("knowledge_search")`）——
  因 `make_knowledge_search_tool` 已随 13 个工厂收敛进 `make_builtin_tool`，该符号不再存在。
- 增量断言：`rg "langchain[./]tools|langchain import tools"` 在 `packages/`、`tests/`、`docs/`
  归零（仅 `docs/superpowers/{specs,plans}/2026-09-16-*.md` 允许残留——那些描述本次重构自身）。
  **必须含斜杠形式** `langchain/tools`：只查点号形式会漏掉 5 处（含 `docs/guides/ai-stack.md`
  这条教人往已删除文件里加工具的可执行指南）。
- 五道门禁：`ruff format --check`、`ruff check`、`lint-imports`（6 契约）、`export_openapi --check`、
  `python -m pytest`（全量）。
  **注意 `export_openapi --check` 的作用域**：它只保护 **HTTP API 契约**，对工具 schema 完全无感
  （实测快照对工具 DTO 与工具文案痕迹为零；`mcp__` 的少数命中是 FastAPI 由 URL 段生成的
  `operationId`，与 MCP 工具名无关）。故**不得**因它变绿就认为工具 schema 未被改动——
  工具 schema 的护栏**只有** §7.1 的契约测试。此门禁的价值在于确认本分支没有意外触碰 HTTP 接口面。

预期计数：基线 **1079** → 最终 **1118**（新增 `tests/tenant/tools/test_toolkit_contract.py` 共 39 条
用例）。实际数以实测为准并记录，**不为了对齐估计值而增删用例**。

## 8. 风险

| # | 风险 | 对策 |
|---|---|---|
| R1 | 单构造器误把 4 个同步平台工具变异步（`StructuredTool` 会静默接受） | `ToolDecl.is_async` + §7.1.4 的方向性断言 |
| R2 | 抄错 description / schema 绑定 | §7.1.1 的全量冻结测试，**重构前先绿** |
| R3 | 漏写某个工具的占位报错体（原本抄 13 遍） | 结构上不可能：报错体只存于构造器一处 |
| R4 | 漏改调用点 | 导入期 `ImportError`；且 `rg "langchain[./]tools\|langchain import tools"` 归零作为收口判据（**只查点号形式不足**——它看不见斜杠写法，实测漏掉 5 处，见 §7.2 与 §10） |
| R5 | 文档 / docstring 里的旧路径 | 已定位 `miles_core/models/tool/__init__.py:4` 的 docstring 提到 `integrations.langchain.tools`，随改动同步 |
| R6 | 子包内出现环 | `catalog → {inputs, specs, naming}` 单向；`lint-imports` 6 契约须仍全绿 |
| R7 | 与 `miles_portal/tenant/tools/` 语义混淆 | 已在 §4 界定：前者是 schema 构造，后者是租户域 CRUD / 执行分发 |

## 9. 遗留

- ~~MCP 命名规则 `compose_mcp_tool_name` 的 64 字符截断 + 短哈希碰撞，当前靠「4 位十六进制」，
  理论上存在碰撞（服务名极多时）。不在本次范围，此处仅登记。~~ → **已处置**（2026-09-18）：
  核实后该条**不只是理论碰撞**，且后果比登记的更重；已在写入侧加守卫，见 §10 与下列更正。
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

### 2026-09-16 实施记录（Task 4 独立终检）

**记数（实测）**
- 基线 **1079** → 最终 **1118 passed**、0 failed、无 warnings summary
  （`uv run --all-packages --group dev python -m pytest -q`）。
- 增量 **39** 条全部来自新增 `tests/tenant/tools/test_toolkit_contract.py`：
  内置契约冻结 13 + spec 驱动契约冻结 4 + 平台同步形状 1 + 分组内容与顺序 1 +
  **声明↔分组双射 1** + opt-in 门控 1 + 装配门控矩阵 1 + 占位报错 13 + spec 驱动占位报错 4。
  与设计预期「基线 1079」一致，未为对齐数字增删任何用例。

**五道门禁（全绿，原始输出）**
| 门禁 | 结果 |
|---|---|
| `ruff format --check .` | `962 files already formatted`，exit 0 |
| `ruff check .` | `All checks passed!`，exit 0 |
| `lint-imports` | `Analyzed 758 files, 2515 dependencies.` / 6 契约全 `KEPT` / `Contracts: 6 kept, 0 broken.`，exit 0 |
| `python -m miles_server.scripts.export_openapi --check` | `OpenAPI snapshot OK`，exit 0（作用域见下 §7.2 修订） |
| `python -m pytest -q` | `1118 passed in 12.55s`，exit 0 |

**契约测试独立证伪（在最终代码上重验 3 个不同不变量）**
变异目标已从 Task 1 时的 13 个分散工厂收敛到 `catalog.py`，故必须重验。
每次变异后均以 `git checkout -- <path>` 还原，`git status --porcelain` 为空，还原后复跑
`39 passed`；未提交任何变异，未改动 `test_toolkit_contract.py` 本身。

1. **抄写保真**——`_DECLS` 中 `generate_video` 的 description 删去末尾 `。`
   → **FAIL**：`test_builtin_tool_contract_frozen[generate_video]`，
   `AssertionError: generate_video 的 description 被改动`（`test_toolkit_contract.py:87`）；
   `1 failed, 38 passed`。
2. **同步/异步形状**——删除 `"calculator"` 声明的 `is_async=False`（落回默认 `True`）
   → **FAIL**：`test_builtin_tool_contract_frozen[calculator]`，
   `AssertionError: calculator 的同步/异步形状被改动`（`:88`）；
   且 `test_platform_tools_are_synchronous`，`AssertionError: calculator 应使用同步 func`（`:97`）；
   `2 failed, 37 passed`。
3. **占位必须报错**——`build_stub_tool` 异步占位 `raise RuntimeError(message)` 改为 `return {}`
   → **FAIL**：13 条失败（`test_builtin_stub_raises_instead_of_executing` 9 条 +
   `test_spec_driven_stub_raises_instead_of_executing` 4 条），
   消息均为 `Failed: DID NOT RAISE <class 'RuntimeError'>`（`:279` / `:286`），
   其中 `[web_search]` 为 `:279`；`13 failed, 26 passed`。

结论：**契约测试在最终代码上仍具判别力**，三类不变量各有独立拦截点。

**非目标核对（按改动「性质」判定，非行数）**
- `miles-portal` 恰好 **6 文件**（numstat 1/1、1/1、1/1、5/3、3/7、1/1）。逐文件通读 diff：
  只出现 (a) import 语句指向 `toolkit/*`、(b) docstring/注释中的路径文案两类改动；
  **无任何语句级逻辑变化**（函数体、条件、参数、返回值均未动）。
- `miles-core/src/miles_core/infra/db` 的 `main...HEAD` diff **为空**（未触碰 DB 会话层）。
- `rg "langchain[./]tools|langchain import tools" backend/packages backend/tests docs`
  （排除 `docs/superpowers/{specs,plans}/2026-09-16-*`）**零命中**，exit 1。
- `toolkit/__init__.py` 为 **0 字节**（硬约束：未构成再导出壳）；旧 `tools.py`（617 行）已删除。

**§7.1 清单之外的第六条断言：声明 ↔ 分组双射（不变量，勘误 8）**
`test_decl_registry_and_groups_are_in_bijection` 断言 `_DECLS` 键集与四个分组元组
（`_PLATFORM_SLUGS` / `_OPT_IN_SLUGS` / `_SKILL_SLUGS` / `_GENERATIVE_SLUGS`）的并集完全相等，
且任一 slug 不得同时归入两个分组。§7.1 的 1–5 条**全部只冻结输出**，本条性质不同，故已作为
第 6 条写入 §7.1 正文并在本节登记。理由：`_DECLS` 只在 `_DECLS[slug]` 处查表、**从不被遍历**，
可见性完全取决于是否落在某个分组元组里——只加声明不加分组时工具**静默缺席且不报错**，
1–5 条都抓不到；而 `docs/guides/ai-stack.md` 正是教贡献者新增内置工具的可执行指南，
走的恰是「加声明」这条路径。该用例来自复评 m1，是本次补入的护栏。

**与设计正文的偏差（均已同步修正正文对应章节）**
1. §5.2：`ToolDecl` **不设** `slug` 字段，slug 由声明表的键承载（`_DECLS: dict[str, ToolDecl]`），
   省去 13 次重复书写；行为无差异。
2. §7.1.2：由「3 个 spec 驱动工具」改为「**4 类**样例」。第 4 类 `mcp(input_schema=None)`
   会让整个 `args_schema` kwarg 被省略、由占位签名反推 schema，是独立风险点，已纳入
   `_EXPECTED_SPEC_DRIVEN` 冻结。
3. §7.1.3：占位报错断言**直接调用占位函数本体**（`_call_stub`：`tool.func()` /
   `asyncio.run(tool.coroutine())`），**不用** `invoke` / `ainvoke`——后者会先过 pydantic 校验，
   空参先抛 `ValidationError`（实测 `calculator.invoke({})` → `ValidationError: Field required`），
   测不到占位体。占位统一为 `**kwargs`，故按签名适配。
4. §7.2：更正 `export_openapi --check` 的作用域（勘误 7）。实测快照
   `backend/openapi/openapi.snapshot.json` 对工具 DTO 与工具文案的痕迹为**零**，该门禁只覆盖
   **HTTP API 契约**，对工具 schema **完全无感**；工具 schema 的**唯一**护栏是契约测试。
   原稿「OpenAPI 快照尤其关键——13 个 DTO 的 description 会进 function schema」为错误断言，已删除。
5. §7.2：收口判据由点号形式 `langchain\.tools` 改为 `langchain[./]tools|langchain import tools`
   （勘误 6）——原形式漏掉斜杠形式与 `import tools` 形式共 5 处，其中包含
   `docs/guides/ai-stack.md` 这条教人往已删除文件里加工具的可执行指南。
6. §3 目标 1 的「均 <200 行」**未达成**：`catalog.py` 实测 **226 行**（非空行 177，
   其中 49 空行 + 4 注释行），超出 26 行；`inputs.py` 118 / `specs.py` 103 / `naming.py` 72 达标。
   超出来源是必须**逐字**内联的 `_DECLS` 声明块（13 条 description 最长 77 字符）与模块
   docstring，「单一职责」仍成立。**未改代码、未改上表目标数值以使其通过**，偏差在此登记，
   并已在 §3 目标 1 处以实施修订脚注标注实测值。

   **裁决（控制者，终检后）：接受该偏差，目标数值维持不改。** 三条理由——
   (a) 「均 <200 行」是**手段**而非目的：它服务于「不再出现 617 行的 god module」这一意图，
   226 行中实质代码 173 行已充分达成该意图；为 26 行改结构属**为对齐数字而改设计**，与本计划
   既定的「不为了对齐估计值而增删用例」同源禁忌。
   (b) `_DECLS` 是**审计对象**——一张表能一眼看全 13 个工具的定义；把声明块迁出以压行数，
   会使「声明 ↔ 分组」的一致性更难人工核对，而该一致性正是本轮新增护栏
   （§7.1 第 6 条）所保护的对象，属**负价值**。
   (c) 226 行含 49 行空行 + 4 行注释，行数指标本身受排版影响，不适合作为硬门槛。

### 2026-09-16 终检后的补充修正（控制者）

Task 4 的 Step 5 只收到「必记勘误 8」一条，故其修订覆盖了我事后核对出的 8 处偏差中的 5 处。
以下 3 处为**终检后由控制者补修**，均已实测确认与实现不符：

1. **§7.1 第 5 条**：原写「工具名**集合**」——实现用的是**精确有序列表**（装配顺序本身是
   对外行为，集合既看不出顺序也发现不了重复工具）。已改为有序并补上理由。
2. **§8 风险表 R4**：仍用点号形式 `langchain\.tools` 作收口判据——同一勘误的第 3 个漏网点
   （前两个是 §7.2 正文与 Global Constraints）。已改为三形式并标注为何点号形式不足。
3. **§7.2「既有 4 个测试文件仅改导入路径」**：实测 `test_knowledge_search_coexistence.py`
   另有一处**函数改名**与调用改写（`make_knowledge_search_tool()` →
   `make_builtin_tool("knowledge_search")`，因该符号已随 13 个工厂收敛进 `make_builtin_tool`）。
   措辞已放宽，避免后人据「仅改导入路径」误判该文件有多余改动。

**教训（已记入计划的自检记录）**：勘误 6 的修正当时只落到 Task 3/4 的**步骤**上，未同步
扫全文中同一形式的其他出现点（Global Constraints、§7.2、§8 R4）。**修正一条勘误时，必须
按「形式」而非「位置」全仓扫一遍**——同类断言往往在多处复述。

**终检时的基线 HEAD**：`0047bbd6`（本记录随其后的 docs-only 提交落地）。

### 2026-09-18 后续：portal 侧 `tools/` 的名字消歧（本文档路径已过时）

本 spec 的模块清单里出现的 `tools/services/custom_tools.py` 已更名为
`tools/services/agent_tool_assembly.py`；`tools/builtins/` 已更名为 `tools/handlers/`
（该包只放 handler，与内置/自定义无关的纯函数上浮为 `tools/primitives.py`）。
原因与范围见该次提交：原三名 `builtin_registry.py` / `builtins/` / `invoke/builtin.py`
各指「声明 / 实现 / 分发」，且 `custom_tools.py` 的主职责（`assemble_agent_tools`）
聚合的是自定义 + MCP + 内置，名字只说 custom 属于以偏概全。此处仅保留历史叙述，
不再回改正文。

### 2026-09-18 更正并处置 §9 第 1 条（MCP 命名碰撞）

原记录写「理论上存在碰撞（服务名极多时）」。实测**两点更正**：

1. **不是纯概率问题**：`service_ident` 的直通路径（纯 ASCII 名）不加摘要，而清洗路径会追加
   4 位摘要，两个命名空间不互斥 —— 所以每个被清洗的服务都存在一个**必然**撞上它的 ASCII 名字
   （把新服务名起成对手的 ident 即可，无需哈希运气）。实测 `MCP示例·知识检索` → ident
   `MCP_ba35`，再建名为 `MCP_ba35` 的服务即得到逐字节相同的 slug。真正纯概率的只有
   4 位摘要之间的生日碰撞（清洗后同形者，如若干纯中文名都塌缩成 `svc`）。
2. **后果比「碰撞」更重**：派发侧 `resolve_mcp_tool_meta` / `invoke_mcp_tool_by_slug` 都是
   `load_tenant_mcp_services` → `find_mcp_tool` 取**首个**匹配，即按**全租户**服务列表比对 slug，
   而非该智能体绑定的服务子集。故 ident 相同时，工具调用会静默落到先被遍历到的那个服务上，
   且被误调的服务**可能根本未被该智能体绑定**。

即：「同租户内服务 ident 唯一」是派发正确性所依赖的不变量，而此前无人在守。

**处置（写入侧守卫，不改命名规则）**：`naming.service_ident`（由 `_service_ident` 提升为公开，
因新增了跨模块消费者）+ 纯函数 `ident_collision`；`McpServiceManager._assert_name_available`
在 `create_service` 与 `update_service`（仅当名字实际变化时）调用，冲突则 `BadRequestError`
并指出与之冲突的服务名。选择写侧而非改命名规则的理由：命名改动会影响 LLM 可见的工具名，
而写侧守卫的炸半径为零（ASCII 名逐字节不变，存量列表/调用不受影响）。读侧有意不动，
故存量已冲突的数据仍可读、可改名修出来。

**验证**：命名纯函数 2 例 + 真实入口 2 例（`create_service` / `update_service`，后者含
「名字未变时不校验」的正向控制）；两处守卫调用各做一次删除注入，对应用例分别变红，确认接线
（而非仅判据）被覆盖。
