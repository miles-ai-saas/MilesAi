# F2b 实施计划：自定义工具契约收敛——DB 加载上移 L1，`langchain/tools.py` 净化为纯 schema 构造

> **归档：** 已实施并合并（engine DI 收敛，2026-09-10 校核）。**收敛记录：** [layering.md](../../architecture/layering.md) §8；执行明细见 `.superpowers/sdd/progress.md`。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除 `integrations/langchain/tools.py` 对 `tenant.tools.{invoke,models,parameters}` 的全部运行期 import，并把租户自定义工具（`Tool` 表 HTTP/SCRIPT 行）的 **DB 加载上移 L1**——`tools.py` 变为纯 schema 构造库（无 DB、无执行），自定义工具经**中性 spec**（L1 loader 产出自 ORM）构造 StructuredTool；`tool_agent/loop.py` 不再调 DB 版 `get_all_platform_tools`，改由 L1 装配后经新入参 `platform_tools` 传入。

**完成标准：**
- `tools.py` 内 `from app.tenant.tools` import 清零（tools.py 净）。
- `loop.py` 不再 import `get_all_platform_tools`；其 `tenant.tools.{confirmation,invoke}` 执行/确认依赖**保留**（F2c 范围）。
- `tenant.tools.models.Tool`/`ToolType` 的 DB `select` 只出现在 L1（新 loader 模块）。
- 全量测试 ≥ 456 passed，无行为变化。

## 背景事实（已审计）

- `loop.py` 的 `StructuredTool` **从不被真执行**：主循环所有工具执行统一走 `invoke_tool_with_context`（loop L85/173/231/364/397）+ `resolve_tool_meta`（确认/元数据）+ 捕获 `ToolConfirmationRequired`；`StructuredTool` 仅经 `_tools_to_openai_schema` 转为 LLM 描述（name/description/args_schema）。故 `tools.py` 内全部 `func`/`_arun` 执行体（`safe_calculate`、httpx、`invoke_custom_http` 等）可占位化（raise「请通过 invoke_tool_with_context 执行」），**行为等价**。
- `get_all_platform_tools` 唯一调用者 = `loop.py` L59；`invoke_platform_tool` wrapper 在 `backend/app` 无任何调用者（dead，可删）。
- `run_tool_calling_chat` 唯一 L1 调用者 = `chat_rag.py` 两分支（L231/L265，形态一致：此前已把输入区参数写入 `agent.config`）。

**Architecture:**

- **L3 中性 spec**：`CustomToolSpec` dataclass（`tools.py` 定义）：
  ```python
  @dataclass(frozen=True)
  class CustomToolSpec:
      """租户自定义工具的 L3 中性描述（L1 loader 自 ORM 构造）。"""
      slug: str
      name: str
      description: str | None
      tool_type: str  # "http" | "script"
      parameters: list[dict]
  ```
- **L3 纯构造**：`build_platform_tools(agent_config: dict, custom_specs: list[CustomToolSpec]) -> list[StructuredTool]`（同步；无 db/ctx）——内置 4 + skill（`cfg.skill_package_id`）+ generative（`cfg.enable_generative_tools`）+ custom specs → schema；`make_custom_http_tool`/`make_custom_script_tool` 改收 `CustomToolSpec`；全部 `func`/`_arun` 占位 raise。原 `get_all_platform_tools`（async，查 DB）删除（无净消费者）；`invoke_platform_tool` 删除。
- **L1 loader**（`tenant/tools/services/custom_tools.py`）：`load_custom_tool_specs(db, ctx) -> list[CustomToolSpec]`——复刻原 `load_tenant_custom_tools` 的 DB 查询（`tenant_filters` + `append_not_deleted` + `Tool.tool_type.in_([ToolType.HTTP, ToolType.SCRIPT])` + `is_active`），行 → `CustomToolSpec`（import `CustomToolSpec` from `integrations.langchain.tools`，L1→L3 合法）。模块不 import L3 StructuredTool（只 spec）。
- **L1 装配**：`chat_rag.py` 两调用点前各插一行装配并给 `run_tool_calling_chat` 传新入参 `platform_tools`：
  ```python
  platform_tools = await assemble_agent_tools(self.db, self.ctx, agent.config or {})
  ```
  装配函数放 `tenant/tools/services/custom_tools.py`：`assemble_agent_tools(db, ctx, agent_config) -> list[StructuredTool]`（`load_custom_tool_specs` + `build_platform_tools(agent_config, specs)`）。两处 import/插入复用同一 helper。
- **loop.py**：`run_tool_calling_chat(..., platform_tools: list[StructuredTool])` 新关键字入参，L59 改 `all_tools = platform_tools`；删 `get_all_platform_tools` import；保留净 import `get_skill_bound_tools`（allowed 分支 skill 兜底追加）。模块 docstring 流程描述同步。

## Global Constraints

- 分层：改后 `tools.py` 无 `from app.tenant.tools`；`loop.py` 保留的 `tenant` import 仅 `tenant.tools.{confirmation,invoke}`（**不得改**，F2c）；`tenant/tools/services/custom_tools.py` 为 L1（可 import L3 `integrations.langchain.tools` 的 spec/构造）。新增 import 均向下（L1→L3 / L3→models/common），禁止反向。
- **行为等价**：StructuredTool 的 name/description/args_schema 与现网完全一致（内置名与描述不变；自定义工具 description/name/slug/schema 映射同旧 `make_custom_*`）。func/_arun 占位化后必须全量测试证明无路径依赖执行体。
- 中文 docstring；改动文件 ≤ 500 行。
- 测试：每任务定向 + 全量回归（基线 **456 passed**；`uv run` 脏 `backend/uv.lock` 须还原）。收尾 ≥ 456。
- 提交：每任务独立 commit，简体中文 `<type>(<scope>): <简述>`（scope `engine`）。

---

### Task 1: `tools.py` 净化——spec + 纯构造 + 占位化 + 删 dead wrapper

**Files:**
- Modify: `backend/app/integrations/langchain/tools.py`

**Interfaces:**
- Produces（Task 2/3 消费，签名精确）:
  - `CustomToolSpec` dataclass（见上，字段语义与原 `Tool` 行一致）
  - `build_platform_tools(agent_config: dict, custom_specs: list[CustomToolSpec]) -> list[StructuredTool]`
  - `make_custom_http_tool(spec: CustomToolSpec) -> StructuredTool`、`make_custom_script_tool(spec: CustomToolSpec) -> StructuredTool`
  - 保留：`get_platform_tools()`（去掉 `ctx` 参数）、`get_skill_bound_tools()`、`get_generative_tools()`
- Removes: `get_all_platform_tools`、`invoke_platform_tool`、`load_tenant_custom_tools` 及全部 `from app.tenant.tools...` import、httpx/datetime/ZoneInfo 等仅执行体用的 import。

- [ ] **Step 1: 确认 dead wrapper 无引用**

Run（backend/ 下）：
```bash
rg -n "invoke_platform_tool|get_all_platform_tools|load_tenant_custom_tools" app tests
```
Expected：仅 `integrations/langchain/tools.py` 与 `integrations/langchain/tool_agent/loop.py` 命中（loop 的 import 将在 Task 3 移除）。

- [ ] **Step 2: 重构 `tools.py`**

- 顶部：`from dataclasses import dataclass`；删 `from app.tenant.tools...`、`httpx`、`datetime`/`zoneinfo`、`select`/`AsyncSession`（如仅 DB 用）、`append_not_deleted`、`tenant_filters` 等 import；保留 pydantic/StructuredTool/uuid。
- 模块 docstring 改为描述纯 schema 构造库职责（内置工具/技能/生成工具壳 + 租户自定义工具经 `CustomToolSpec`；执行统一走 L1 `invoke_tool_with_context`，本模块 `func` 均占位）。
- 新增 `CustomToolSpec` dataclass。
- 工具构造函数改造（语义保持 name/description/args_schema）：
  - `_make_calculator_tool`/`_make_http_request_tool`/`_make_datetime_tool`/`make_knowledge_search_tool()`/skill/generative 各 `_run`/`_arun`：改为 `raise RuntimeError("请通过 invoke_tool_with_context 执行 <slug>")`（calculator/http/datetime 由占位代替原执行体；`make_knowledge_search_tool` 删 `ctx` 参数）。
  - `make_custom_http_tool(spec)`：`schema = parameters_to_pydantic(spec.parameters)`；`_arun` 占位 raise。
  - `make_custom_script_tool(spec)`：同上。
- 删除 `load_tenant_custom_tools`、`get_all_platform_tools`、`invoke_platform_tool`。
- 新增 `build_platform_tools`（函数代码 verbatim）:

```python
def build_platform_tools(
    agent_config: dict | None,
    custom_specs: list[CustomToolSpec] | None = None,
) -> list[StructuredTool]:
    """构造画布/对话工具 schema 列表（纯函数，不查 DB、不执行）。

    内置工具 + 绑定技能包 ``skill_*`` + ``enable_generative_tools`` 时的
    ``generate_*`` + 租户自定义 HTTP/SCRIPT 工具（``CustomToolSpec``）。
    ``agent_config`` 缺失时仅内置工具。
    """
    cfg = agent_config if isinstance(agent_config, dict) else {}
    tools = get_platform_tools()
    if cfg.get("skill_package_id"):
        tools = [*tools, *get_skill_bound_tools()]
    if cfg.get("enable_generative_tools"):
        tools = [*tools, *get_generative_tools()]
    for spec in custom_specs or []:
        if spec.tool_type == "http":
            tools.append(make_custom_http_tool(spec))
        elif spec.tool_type == "script":
            tools.append(make_custom_script_tool(spec))
    return tools
```

- [ ] **Step 3: 验证 + 回归**

Run（backend/ 下）：
```bash
rg -n "from app\.tenant\.tools|import app\.tenant\.tools" app/integrations/langchain/tools.py || echo "tools.py 对 tenant.tools 引用清零"
rg -n "safe_calculate|invoke_custom_http|httpx|ToolType|Tool\b" app/integrations/langchain/tools.py || echo "执行体/ORM/纯函数依赖已净"
uv run ruff check app/integrations/langchain/tools.py
uv run python -m pytest -q | tail -1
```
Expected：rg 无命中、ruff 全绿、pytest ≥ 456（**此刻 loop.py 仍 import 已被删除的 `get_all_platform_tools` → 预期收集 ImportError，需 Task 3 同步。若跑挂，以"已知 Task 3 未接"记录，仍应保证除 loop 外无其它 ImportError——用 `pytest tests/tenant/tools tests/integrations -q` 定向兜底确认本文件改动自身无错**）。

> 注：若发现 Step 3 全量无法绿（loop 引用删除符号），允许 Task 1 与 Task 3 在同一次实现会话连续完成后再跑全量——由 Task 3 的 Step 2 全量收口；Task 1 commit 前至少保证 `python -c "import app.integrations.langchain.tools"` 成功 + ruff 绿。

- [ ] **Step 4: Commit**

```bash
git add backend/app/integrations/langchain/tools.py
git commit -m "refactor(engine): langchain/tools.py 净化为纯 schema 构造库

租户自定义工具改经 CustomToolSpec 中性描述；内置/技能/生成壳 func 占位
（主循环从不执行 StructuredTool），DB 查询与执行依赖移出 L3。"
```

---

### Task 2: L1 loader + 装配 helper

**Files:**
- Create: `backend/app/tenant/tools/services/custom_tools.py`

**Interfaces:**
- Consumes: Task 1 `CustomToolSpec`/`build_platform_tools`（`integrations.langchain.tools`）、`Tool`/`ToolType`（`tenant.tools.models`）、`tenant_filters`/`append_not_deleted`。
- Produces:
  - `load_custom_tool_specs(db: AsyncSession, ctx: TenantContext) -> list[CustomToolSpec]`
  - `assemble_agent_tools(db: AsyncSession, ctx: TenantContext, agent_config: dict | None) -> list[StructuredTool]`

- [ ] **Step 1: 实现（代码 verbatim）**

```python
"""租户自定义工具 DB 加载与对话工具装配（L1）。

``load_custom_tool_specs``：``Tool`` 表 HTTP/SCRIPT 行 → 中性 ``CustomToolSpec``；
``assemble_agent_tools``：specs + 内置/技能/生成壳（``build_platform_tools``）组装
为对话工具 schema 列表。原 ``integrations/langchain/tools.load_tenant_custom_tools``
的 DB 查询职责上移本模块，L3 只保留纯构造。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.soft_delete import append_not_deleted
from app.core.tenant import TenantContext, tenant_filters
from app.integrations.langchain.tools import CustomToolSpec, build_platform_tools
from app.tenant.tools.models import Tool, ToolType


async def load_custom_tool_specs(db: AsyncSession, ctx: TenantContext) -> list[CustomToolSpec]:
    """加载租户启用的自定义 HTTP / 脚本工具为中性 spec（不构造 StructuredTool）。"""
    filters = append_not_deleted(tenant_filters(ctx, Tool.tenant_id), Tool)
    rows = (
        (
            await db.execute(
                select(Tool).where(
                    *filters,
                    Tool.is_active.is_(True),
                    Tool.tool_type.in_([ToolType.HTTP, ToolType.SCRIPT]),
                )
            )
        )
        .scalars()
        .all()
    )
    return [
        CustomToolSpec(
            slug=t.slug,
            name=t.name,
            description=t.description,
            tool_type=t.tool_type.value if hasattr(t.tool_type, "value") else str(t.tool_type),
            parameters=list(t.parameters or []),
        )
        for t in rows
    ]


async def assemble_agent_tools(
    db: AsyncSession,
    ctx: TenantContext,
    agent_config: dict | None,
) -> list:
    """装配对话工具 schema 列表（specs 上移 L1 + L3 纯构造）。"""
    specs = await load_custom_tool_specs(db, ctx)
    return build_platform_tools(agent_config, specs)
```

（`tool_type` 映射若实际为 str 枚举值，以现网 `Tool.tool_type` 行为一致为准——旧代码 `ToolType.HTTP` 枚举成员与 `make_custom_*` 分支比较 `t.tool_type == ToolType.HTTP`；`CustomToolSpec.tool_type` 统一存**枚举 value 字符串** `"http"`/`"script"`，`build_platform_tools` 分支比较字符串。若 `ToolType` 是 str Enum，`.value` 即 `"http"`；实现时确认一次 `tenant/tools/models.py` 的 `ToolType` 定义，必要时 loader 直接 `str(ToolType(t.tool_type).value)`。）

- [ ] **Step 2: 验证**

Run（backend/ 下）：
```bash
rg -n "from app\.tenant\.tools\.invoke|from app\.tenant\.tools\.models" app/tenant/tools/services/custom_tools.py
uv run ruff check app/tenant/tools/services/custom_tools.py
uv run python -c "import app.tenant.tools.services.custom_tools" 
```
Expected：仅 models import（L1 内合法）；ruff 全绿；import 成功。全量 pytest 待 Task 3 接线后跑。

- [ ] **Step 3: Commit**

```bash
git add backend/app/tenant/tools/services/custom_tools.py
git commit -m "refactor(engine): 自定义工具 DB 加载上移 L1 loader/装配 helper

load_custom_tool_specs 产出中性 CustomToolSpec，assemble_agent_tools
供 chat 装配对话工具列表。"
```

---

### Task 3: `loop.py` 入参化 + `chat_rag.py` 装配接线

**Files:**
- Modify: `backend/app/integrations/langchain/tool_agent/loop.py`
- Modify: `backend/app/tenant/agents/services/agent/chat_rag.py`

**Interfaces:**
- Consumes: Task 1/2 `assemble_agent_tools`。
- Produces: 收敛终态——`loop.py` 不再 import `get_all_platform_tools`（保留 `get_skill_bound_tools` 净 import 与 `tenant.tools.{confirmation,invoke}`）；`run_tool_calling_chat` 新入参 `platform_tools: list`（必传，关键字）。

- [ ] **Step 1: `loop.py`**

- 删 import `get_all_platform_tools`（现 L23：`from app.integrations.langchain.tools import get_all_platform_tools, get_skill_bound_tools` → 保留 `get_skill_bound_tools`）。
- 签名追加：`platform_tools: list,`（建议置于 `usage_sink` 之后；标注类型用 `list` 或 `list[StructuredTool]`——若 `StructuredTool` 未 import 则用 `list` 避免新增 langchain_core import，若已可 import 则精确标注）。
- L59 改：`all_tools = platform_tools`（删 `await get_all_platform_tools(db, ctx, agent_config=agent.config or {})`）。
- 模块 docstring（流程描述）与函数 docstring 同步：工具 schema 由 L1 装配传入（`platform_tools`），本函数不再查 DB。
- 确认 `db`/`ctx` 形参仍被其余逻辑使用（media resolve/invoke 需 db/ctx——保留，勿删形参）。

- [ ] **Step 2: `chat_rag.py` 装配接线**

两处 `run_tool_calling_chat(...)` 调用点（L231 分支与 L265 分支，形态一致）：在各分支调用前插入装配，并加传参：

```python
                from app.tenant.tools.services.custom_tools import assemble_agent_tools

                platform_tools = await assemble_agent_tools(self.db, self.ctx, agent.config or {})
```

在 `run_tool_calling_chat(...)` 实参表加 `platform_tools=platform_tools,`（两处各一次；import 放函数内局部即可，与现有 `from app.integrations.langchain.tool_agent import run_tool_calling_chat` 的函数级 import 风格一致——也可模块级 import，视 ruff 与整洁自定，但保持两分支共用）。

- [ ] **Step 3: 验证 + 回归**

Run（backend/ 下）：
```bash
rg -n "get_all_platform_tools" app/integrations/langchain/tool_agent/loop.py || echo "loop.py 不再引用 DB 版工具加载"
rg -n "from app\.tenant\.tools" app/integrations/langchain/tools.py app/integrations/langchain/tool_agent/loop.py
uv run ruff check app/integrations/langchain/tool_agent/loop.py app/tenant/agents/services/agent/chat_rag.py app/tenant/tools/services/custom_tools.py app/integrations/langchain/tools.py
uv run python -m pytest -q | tail -1
```
Expected：第一条 rg 无命中；第二条仅 `loop.py` 命中 `tenant.tools.{confirmation,invoke}`（F2c 预留，允许）；ruff 全绿；pytest ≥ 456 passed。

- [ ] **Step 4: Commit**

```bash
git add backend/app/integrations/langchain/tool_agent/loop.py backend/app/tenant/agents/services/agent/chat_rag.py
git commit -m "refactor(engine): tool_agent 主循环工具列表改由 L1 装配注入

run_tool_calling_chat 增 platform_tools 入参，chat_rag 两分支经
assemble_agent_tools 组装，L3 主循环不再查 Tool 表。"
```

---

### Task 4: 回归审计与 `layering.md` 收敛记录

**Files:**
- Modify: `docs/architecture/layering.md`

- [ ] **Step 1: 全量回归 + rg 终审**

Run（backend/ 下）：
```bash
rg -n "from app\.tenant\.tools|import app\.tenant\.tools" app/integrations/langchain/tools.py app/integrations/langchain/tool_agent/loop.py app/integrations/langchain/tool_agent/artifacts.py || echo "tools 契约面 L3 净（loop 仅剩 F2c 执行面时单独说明）"
uv run ruff check app/integrations/langchain app/tenant/tools/services/custom_tools.py
uv run python -m pytest -q | tail -1
```
Expected：ruff 全绿；rg 无命中（若 loop.py 仍命中 `tenant.tools.{confirmation,invoke}` 属预期，调整断言为 tools.py/artifacts.py 清零）；pytest ≥ 456。

- [ ] **Step 2: 更新收敛记录**

`docs/architecture/layering.md`：
- 在 F2a 收敛记录（`收敛记录（2026-09-09，F2a）`）之后追加：

```markdown
> **收敛记录（2026-09-09，F2b）**：自定义工具契约收敛——租户 `Tool` 表 HTTP/SCRIPT 行 DB 加载上移 L1（`tenant/tools/services/custom_tools.py` 的 `load_custom_tool_specs`/`assemble_agent_tools`），产出中性 `CustomToolSpec`；`integrations/langchain/tools.py` 净化为纯 schema 构造库（`build_platform_tools`，内置/技能/生成壳与自定义 spec→StructuredTool，func 全占位——主循环从不执行 StructuredTool，执行统一走 `invoke_tool_with_context`），删除 DB 版 `get_all_platform_tools` 与 dead wrapper `invoke_platform_tool`；`tool_agent/loop.py` 改收 L1 装配的 `platform_tools` 入参，不再查 `Tool` 表；工具参数三纯函数（`normalize_parameters`/`validate_tool_params`/`parameters_to_pydantic`）下沉中立 `models/tool/parameters.py`（`tenant/tools/parameters.py` 转 re-export shim，消除 Task 1 复刻 drift）（见 plan [`2026-09-09-engine-di-custom-tool-contract`](../superpowers/plans/2026-09-09-engine-di-custom-tool-contract.md)）。`loop.py` 剩余 `tenant.tools.{confirmation,invoke}` 执行/确认行为面与画布 `tool_nodes` 注入待 F2c。
```

- §8 修订记录表（F2a 行之后）追加：

```markdown
| 2026-09-09 | F2b：自定义工具 DB 加载上移 L1 `custom_tools` loader；`langchain/tools.py` 净化为纯 schema 构造（CustomToolSpec/占位壳），loop 工具列表 L1 装配注入；工具参数三纯函数下沉 `models/tool/parameters.py` |
```

- [ ] **Step 3: Commit**

```bash
git add docs/architecture/layering.md
git commit -m "docs(architecture): 记录 F2b 自定义工具契约收敛"
```

---

### Task 5: 工具参数三纯函数下沉中立 `models/tool/parameters.py`（消除 Task 1 复刻）

> 排序说明：Task 1 review 判 [Important] 复刻 drift 风险。本任务紧随 Task 1 完成，消除双份 schema 规则源；Task 3（loop 接线）不受影响。

**Files:**
- Create: `backend/app/models/tool/__init__.py`、`backend/app/models/tool/parameters.py`
- Modify: `backend/app/tenant/tools/parameters.py`（转 re-export shim）、`backend/app/integrations/langchain/tools.py`（删复刻块、改指 models）

**Interfaces:**
- Produces: 中立 `models/tool/parameters.py` 原样承载三函数。
- Consumes: `tools.py` 复刻版删除后改 `from app.models.tool.parameters import parameters_to_pydantic`；`tenant/tools/parameters.py` 变 shim（re-export 三函数，加 `# noqa: F401`，docstring 说明下沉），既有 L1 consumer（`tenant/tools/services/tools.py`、`tenant/tools/invoke/custom.py`）import 路径不变。

- [ ] **Step 1: 中立模块落地**

- 建 `backend/app/models/tool/__init__.py`（空或一行域说明）。
- 新建 `backend/app/models/tool/parameters.py`：正文**逐字节**取自 `tenant/tools/parameters.py` 现文（模块 docstring 改为「工具输入参数 schema 中立规范——校验与动态 Pydantic 模型；L1 `tenant.tools.parameters` 为其 re-export shim，L3 `langchain/tools` 直接引用本模块」），函数体与常量不动。
- `tenant/tools/parameters.py` 改为 shim：
  ```python
  """工具输入参数 schema 校验与动态 Pydantic 模型（re-export shim）。

  三函数已下沉中立 ``models/tool/parameters.py``；本模块保留 L1 import 路径。
  """

  from app.models.tool.parameters import (  # noqa: F401
      normalize_parameters,
      parameters_to_pydantic,
      validate_tool_params,
  )
  ```
- `integrations/langchain/tools.py`：删除「本地复刻」注释块与 `parameters_to_pydantic` 复刻函数（`BaseModel`/`Field`/`create_model`/`BadRequestError` 若仅复刻用则一并清），改 `from app.models.tool.parameters import parameters_to_pydantic`（按现有 import 分组排序）。

- [ ] **Step 2: 验证**

Run（backend/ 下）：
```bash
rg -n "def parameters_to_pydantic|def normalize_parameters|def validate_tool_params" app/integrations/langchain/tools.py app/models/tool/parameters.py app/tenant/tools/parameters.py
diff <(sed -n '/^def /,$p' app/models/tool/parameters.py) <(git show HEAD:app/tenant/tools/parameters.py | sed -n '/^def /,$p') && echo "函数体与下沉前一致" || echo "存在差异（docstring 变更属预期，函数体必须逐字节一致）"
uv run ruff check app/models/tool app/tenant/tools/parameters.py app/integrations/langchain/tools.py
uv run python -c "import app.models.tool.parameters, app.tenant.tools.parameters, app.integrations.langchain.tools"
```
Expected：每个函数仅一处 `def`（tools.py 无）；diff 输出仅 docstring 差异或全一致（若不区分 docstring，直接 diff 全文核对 shim 头部除外）；ruff 全绿；import 成功。shim 守卫测试（断言 `tenant.tools.parameters.normalize_parameters is models.tool.parameters.normalize_parameters`）可选加 `tests/tenant/tools/test_parameters_shim.py`（TDD 不强制）。

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/tool backend/app/tenant/tools/parameters.py backend/app/integrations/langchain/tools.py
git commit -m "refactor(engine): 工具参数纯函数下沉 models/tool，消除 L3 复刻

normalize_parameters/validate_tool_params/parameters_to_pydantic 落中立域，
tenant.tools.parameters 转 shim，langchain/tools 改指共享源。"
```

---

## Self-Review

- **Spec coverage**：目标（`tools.py` 对 `tenant.tools` import 清零、DB 查询仅在 L1、loop 不再 DB 加载）由 Task 1（净构造）+ Task 2（L1 loader/装配）+ Task 3（loop 入参化 + chat_rag 接线）达成；Task 4 文档闭环。
- **行为等价**：占位化前提（loop 从不执行 StructuredTool.func）已由审计事实支撑；name/description/args_schema 不变；工具过滤（`tool_slugs`/skill 兜底追加）仍在 loop 内、语义不变；DB 查询时机与频次不变（每次 chat 一次）。
- **依赖方向**：`custom_tools.py`（L1）→ L3 `build_platform_tools`/`CustomToolSpec` 为合法向下；`loop.py` 保留 F2c 预留面。tools.py 内 func 占位后无任何 import `tenant`。
- **`tool_type` 值约定**：spec 统一存枚举 value 字符串 `"http"`/`"script"`；Task 2 Step 1 要求实现时核对 `ToolType` 定义并按需 `str(...)`/`.value` 规整，build 分支按字符串比较（防 str-Enum 判等歧义）。
- **已知衔接点**：Task 1 Step 3 全量可能因 loop 旧 import 红——Task 1 单独提交以「`import tools` 成功 + ruff 绿」为准；Task 3 Step 3 为全量收口点。若实现者选择 T1+T3 连续完成后再全量亦可（T3 收口）。
- **Placeholder scan**：无 TBD；Task 2/各关键新代码为 verbatim。
