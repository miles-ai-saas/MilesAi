# LangChain 工具 schema 模块拆分与声明式收敛 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 617 行的 `langchain/tools.py` 按职责拆为 `langchain/toolkit/` 4 模块，并把 13 个同形工具工厂收敛为「声明表 + 单一构造器」，对外行为逐字节不变。

**Architecture:** 先写一条**契约冻结测试**钉住全部 16 个工具的 `name`/`description`/`args_schema`/占位报错文案/同步异步形状，再重构。重构分两步走，每步都保持全绿：先纯搬迁出 `naming`/`inputs`/`specs` 三个纯职责模块（`tools.py` 暂作再导出，使 1079 条既有测试继续有效），再建 `catalog.py` 做声明式收敛、删除 `tools.py`、迁移 11 处调用点。

**Tech Stack:** Python 3.11、LangChain `StructuredTool`、pydantic v2、pytest、ruff、import-linter。

**Spec:** `docs/superpowers/specs/2026-09-16-langchain-toolkit-split-design.md`

## Global Constraints

- **工作位置**：worktree `.worktrees/langchain-toolkit-split`，分支 `feat/langchain-toolkit-split`。**不得**在 `main` 或主仓检出目录直接改动。
- **命令前缀**：所有命令在 `backend/` 下执行，且**必须**带 `uv run --all-packages --group dev`。裸 `uv run` / `uv sync` 会卸载其他 workspace 成员包。
- **测试命令**：**必须** `uv run --all-packages --group dev python -m pytest`。**不要**用 console script `pytest`——它不把 CWD 注入 `sys.path`，而 `tests/` 不是包，会在收集期以 `ModuleNotFoundError: No module named 'tests'` 炸掉。
- **五道门禁**（全部在 `backend/` 下，缺一不可）：
  1. `uv run --all-packages --group dev ruff format --check .`
  2. `uv run --all-packages --group dev ruff check .`
  3. `uv run --all-packages --group dev lint-imports`
  4. `uv run --all-packages --group dev python -m miles_server.scripts.export_openapi --check`
  5. `uv run --all-packages --group dev python -m pytest -q`
- **基线测试数**：**1079**（本计划开始时的 `main` = `ea418bd4`）。
- **提交信息**：简体中文，Conventional Commits，HEREDOC 传递；创建新提交，**不 amend**。
- **分层约束**：`miles_ai` ✗→ `miles_portal`；`miles_portal` ✗→ `miles_admin`；`miles_core` ✗→ `miles_ai`。本计划只在 `miles_ai` 包内新增文件，不新增跨包依赖。
- **不引入新依赖**；不改 import-linter 契约；不动 `miles_portal/tenant/tools/`。
- **对外行为逐字节不变**：工具名、description、`args_schema` JSON、占位报错文案、装配顺序、门控判定。
- **`toolkit/__init__.py` 必须为空**（不得构成再导出壳）。最终状态：仓库内**不存在指向旧模块的引用**——验证用 `rg -n "langchain[./]tools" backend/packages backend/tests docs`，只允许命中描述本次重构本身的历史文档（勘误 6：点号形式不足以证明这一点）。

---

## File Structure

| 文件 | 职责 | 动作 |
|---|---|---|
| `backend/tests/tenant/tools/test_toolkit_contract.py` | 契约冻结：16 个工具的对外可观测面 | **新建**（Task 1） |
| `backend/packages/miles-ai/src/miles_ai/integrations/langchain/toolkit/__init__.py` | 空文件（刻意无再导出） | **新建**（Task 2） |
| `.../langchain/toolkit/naming.py` | MCP function name 约定 + 工具白名单过滤 | **新建**（Task 2，自 `tools.py:33-98` 搬迁） |
| `.../langchain/toolkit/inputs.py` | 13 个入参 DTO（纯声明） | **新建**（Task 2，自 `tools.py:189-297` 搬迁） |
| `.../langchain/toolkit/specs.py` | 中性 spec + JSON Schema → pydantic | **新建**（Task 2，自 `tools.py:39,100-188` 搬迁） |
| `.../langchain/toolkit/catalog.py` | 声明表 + 构造器 + 分组 + 选型 + 总装配 | **新建**（Task 2 建壳，Task 3 收敛） |
| `.../langchain/tools.py` | 原 617 行模块 | Task 2 降为临时再导出；**Task 3 删除** |
| 生产 7 处 + 测试 4 处调用点 | 见 Task 3 Step 2 清单 | Task 3 迁移 import |
| `backend/packages/miles-core/src/miles_core/models/tool/__init__.py:4` | docstring 提及旧路径 | Task 3 同步 |

依赖方向（单向无环）：`catalog → {inputs, specs, naming}`；`naming` / `inputs` / `specs` 三者互不依赖。

---

### Task 1: 契约冻结测试（重构前必须先绿）

**Files:**
- Create: `backend/tests/tenant/tools/test_toolkit_contract.py`
- Test: 该文件自身

**Interfaces:**
- Consumes: `miles_ai.integrations.langchain.tools` 的**现状**公开面（`get_platform_tools` / `select_opt_in_builtin_tools` / `get_skill_bound_tools` / `get_generative_tools` / `build_platform_tools` / `CustomToolSpec` / `McpToolSpec`）。
- Produces: 无（纯测试）。本任务**不改任何生产代码**。

> **本任务是「重构前先冻结」的一半。** 期望值是当前实现的**实测产物**（下方已内联，含逐字中文文案与完整 JSON Schema）。重构后这些值**一字不得改**——若重构后需要改期望值才能变绿，说明行为变了，是 bug 而非测试问题。

- [ ] **Step 1: 写契约测试**

```python
"""toolkit 契约冻结：16 个工具的对外可观测面在「拆分 + 声明式收敛」前后必须逐字节一致。

为什么必须存在：重构把 13 个工厂收敛为一张声明表，而 13 条 description 中有 7 条超过
100 字符（最长 199），逐字搬运极易出错；`StructuredTool` 又会**静默接受**把同步工具
写成异步（只是 `.func` 变空、`.coroutine` 非空，调用方看不出来）。本文件是这两类错误
唯一的拦截手段，故在重构**之前**先跑绿。

期望值来源：由重构前的实现实测导出（`args_schema.model_json_schema()` 经
`json.dumps(..., sort_keys=True, separators=(",", ":"))` 归一化），非人工手写。
"""

from __future__ import annotations

import asyncio
import json

import pytest

from miles_ai.integrations.langchain.tools import (
    CustomToolSpec,
    McpToolSpec,
    build_platform_tools,
    get_generative_tools,
    get_platform_tools,
    get_skill_bound_tools,
    select_opt_in_builtin_tools,
)

_OPT_IN_SLUGS = ("web_search", "code_execution", "compliance_check_text", "run_flow_once", "invoke_tenant_hook")

# 每个工具一行：slug -> (description, is_async, args_schema 的归一化 JSON)
# 由重构前的实现实测导出（见 Step 2 的导出脚本），逐字复制，非人工手写。
_EXPECTED_BUILTIN: dict[str, tuple[str, bool, str]] = {
    "calculator": ("安全计算数学表达式", False, '{"properties":{"expression":{"description":"数学表达式，如 1+2*3","title":"Expression","type":"string"}},"required":["expression"],"title":"CalculatorInput","type":"object"}'),
    "http_request": ("发起 HTTP 请求", False, '{"properties":{"method":{"default":"GET","title":"Method","type":"string"},"timeout":{"default":10.0,"title":"Timeout","type":"number"},"url":{"title":"Url","type":"string"}},"required":["url"],"title":"HttpRequestInput","type":"object"}'),
    "get_current_datetime": ("获取当前的日期时间", False, '{"properties":{"timezone":{"anyOf":[{"type":"string"},{"type":"null"}],"default":null,"description":"IANA 时区，默认 UTC","title":"Timezone"}},"title":"DateTimeInput","type":"object"}'),
    "knowledge_search": ("在指定知识库中语义检索", False, '{"properties":{"kb_id":{"anyOf":[{"type":"string"},{"type":"null"}],"default":null,"description":"单个知识库 ID（与 kb_ids 二选一；可省略用智能体已绑定知识库）","title":"Kb Id"},"kb_ids":{"anyOf":[{"items":{"type":"string"},"type":"array"},{"type":"null"}],"default":null,"description":"多个知识库 ID；多库检索时优先使用","title":"Kb Ids"},"limit":{"default":5,"description":"返回片段数","title":"Limit","type":"integer"},"query":{"description":"检索问题","title":"Query","type":"string"}},"required":["query"],"title":"KnowledgeSearchInput","type":"object"}'),
    "web_search": ("使用 DuckDuckGo 搜索网页，返回摘要与相关链接", True, '{"properties":{"max_results":{"anyOf":[{"type":"integer"},{"type":"null"}],"default":null,"description":"返回条数，默认 5","title":"Max Results"},"query":{"description":"搜索关键词","title":"Query","type":"string"}},"required":["query"],"title":"WebSearchInput","type":"object"}'),
    "code_execution": ("在 Runner 沙箱中执行 Python 代码片段（须符合安全校验）", True, '{"properties":{"code":{"description":"Python 代码片段（须定义 run(params) 语义的片段；禁止 import）","title":"Code","type":"string"},"memory":{"anyOf":[{"type":"integer"},{"type":"null"}],"default":null,"description":"内存上限 MB，默认 256","title":"Memory"},"timeout":{"anyOf":[{"type":"integer"},{"type":"null"}],"default":null,"description":"超时秒数，默认 30","title":"Timeout"}},"required":["code"],"title":"CodeExecutionInput","type":"object"}'),
    "compliance_check_text": ("检测文本是否命中租户敏感词库，返回命中词与 warn/block 处置建议（只读）", True, '{"properties":{"text":{"description":"待检测文本","title":"Text","type":"string"}},"required":["text"],"title":"ComplianceCheckTextInput","type":"object"}'),
    "run_flow_once": ("执行本租户一个已发布流程一次并返回其输出；仅限已发布流程，执行前需用户确认", True, '{"properties":{"flow_id":{"description":"已发布流程的 UUID","title":"Flow Id","type":"string"},"inputs":{"anyOf":[{"additionalProperties":true,"type":"object"},{"type":"null"}],"default":null,"description":"流程入口变量字典，如 {\\"query\\": \\"...\\"}","title":"Inputs"},"query":{"anyOf":[{"type":"string"},{"type":"null"}],"default":null,"description":"便捷传入流程 query 入口变量","title":"Query"},"timeout_sec":{"anyOf":[{"type":"integer"},{"type":"null"}],"default":null,"description":"执行超时秒数，默认 120，上限 300","title":"Timeout Sec"}},"required":["flow_id"],"title":"RunFlowOnceInput","type":"object"}'),
    "invoke_tenant_hook": ("手动触发本租户已绑定的 HTTP 钩子（按触发时机与作用域），返回各钩子状态与改写后的载荷", True, '{"properties":{"payload":{"anyOf":[{"additionalProperties":true,"type":"object"},{"type":"null"}],"default":null,"description":"传给钩子的载荷，如 {\\"query\\": \\"...\\"}","title":"Payload"},"scope":{"anyOf":[{"type":"string"},{"type":"null"}],"default":null,"description":"作用域：global（默认）/ agent / flow / tool / app","title":"Scope"},"target_id":{"anyOf":[{"type":"string"},{"type":"null"}],"default":null,"description":"作用域目标 ID（非 global 时使用）","title":"Target Id"},"trigger":{"description":"触发时机：before_call / after_call / before_reasoning / after_reasoning / before_tool / after_tool / on_error","title":"Trigger","type":"string"}},"required":["trigger"],"title":"InvokeTenantHookInput","type":"object"}'),
    "skill_read_reference": ("读取绑定技能包 references/ 或 assets/ 下的文本文件", True, '{"properties":{"max_chars":{"anyOf":[{"type":"integer"},{"type":"null"}],"default":null,"description":"最大读取字符数，默认 12000","title":"Max Chars"},"path":{"description":"相对技能根的路径，如 references/guide.md","title":"Path","type":"string"}},"required":["path"],"title":"SkillReadReferenceInput","type":"object"}'),
    "skill_run_script": ("在沙箱中执行绑定技能包 scripts/ 下的 Python 脚本", True, '{"properties":{"max_memory_mb":{"anyOf":[{"type":"integer"},{"type":"null"}],"default":null,"description":"内存上限 MB，默认 512","title":"Max Memory Mb"},"params":{"additionalProperties":true,"description":"传入 run(params) 的参数字典","title":"Params","type":"object"},"path":{"description":"scripts/ 下脚本路径，如 scripts/example.py","title":"Path","type":"string"},"timeout_sec":{"anyOf":[{"type":"integer"},{"type":"null"}],"default":null,"description":"超时秒数，默认 30","title":"Timeout Sec"}},"required":["path"],"title":"SkillRunScriptInput","type":"object"}'),
    "generate_image": ("生成图片（文生图/图生图）。直接通过 function calling 调用，传入 prompt 等参数即可，禁止在文字中描述调用过程。", True, '{"properties":{"image_attachment_id":{"anyOf":[{"type":"string"},{"type":"null"}],"default":null,"description":"参考图 attachment_id（如用户上传了图片并提供其 ID 时才填，通常不填）","title":"Image Attachment Id"},"model_config_id":{"anyOf":[{"type":"string"},{"type":"null"}],"default":null,"description":"生图模型 ID，留空自动使用默认模型，通常不需要填写","title":"Model Config Id"},"n":{"anyOf":[{"type":"integer"},{"type":"null"}],"default":null,"description":"独立单图张数 1–4（不是一张图里的格子数）；≥3 需用户确认","title":"N"},"prompt":{"description":"单幅完整画面描述。n>1 时仍写单图内容；除非用户明确要求组图/宫格/拼接，禁止四宫格或分镜拼贴","title":"Prompt","type":"string"},"size":{"anyOf":[{"type":"string"},{"type":"null"}],"default":null,"description":"如 1024x1024；≥1280 边长或多张需用户确认","title":"Size"}},"required":["prompt"],"title":"GenerateImageInput","type":"object"}'),
    "generate_video": ("生成短视频（文/图生视频）。直接通过 function calling 调用，传入 prompt 等参数即可，禁止在文字中描述调用过程。耗时长，异步排队。", True, '{"properties":{"duration":{"anyOf":[{"type":"integer"},{"type":"null"}],"default":null,"description":"时长秒数，默认 5","title":"Duration"},"image_attachment_id":{"anyOf":[{"type":"string"},{"type":"null"}],"default":null,"description":"首帧图 attachment_id（如用户上传了图片并提供其 ID 时才填，通常不填）","title":"Image Attachment Id"},"last_frame_attachment_id":{"anyOf":[{"type":"string"},{"type":"null"}],"default":null,"description":"尾帧图 attachment_id（首尾帧生视频，须与首帧同传，通常不填）","title":"Last Frame Attachment Id"},"model_config_id":{"anyOf":[{"type":"string"},{"type":"null"}],"default":null,"description":"生视频模型 ID，留空自动使用默认模型，通常不需要填写","title":"Model Config Id"},"prompt":{"description":"视频描述","title":"Prompt","type":"string"},"resolution":{"anyOf":[{"type":"string"},{"type":"null"}],"default":null,"description":"720P 或 1080P","title":"Resolution"}},"required":["prompt"],"title":"GenerateVideoInput","type":"object"}'),
}

# spec 驱动：slug -> (description, is_async, schema JSON)
_EXPECTED_SPEC_DRIVEN: dict[str, tuple[str, bool, str]] = {
    "my_http": ("自定义 HTTP 工具", True, '{"properties":{"q":{"description":"查询词","title":"Q","type":"string"}},"required":["q"],"title":"ToolParams","type":"object"}'),
    "my_script": ("My Script", True, '{"properties":{"n":{"default":null,"description":"次数","title":"N","type":"integer"}},"title":"ToolParams","type":"object"}'),
    "mcp__github__create_issue": ("创建 issue", True, '{"properties":{"n":{"anyOf":[{"type":"integer"},{"type":"null"}],"default":3,"title":"N"},"title":{"description":"标题","title":"Title","type":"string"}},"required":["title"],"title":"McpToolParams","type":"object"}'),
    # 勘误 3 新增：input_schema=None 时 args_schema 缺省，schema 由占位签名反推（title 取工具名）
    "mcp__svc__nofields": ("svc · nofields", True, '{"properties":{"kwargs":{"additionalProperties":true,"default":null,"title":"Kwargs","type":"object"}},"title":"mcp__svc__nofields","type":"object"}'),
}


def _normalized(tool) -> str:
    """把 args_schema 归一化为可比字符串（键序固定、无多余空白）。"""
    return json.dumps(tool.args_schema.model_json_schema(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _all_builtin() -> dict:
    tools = [
        *get_platform_tools(),
        *select_opt_in_builtin_tools({"tool_slugs": list(_OPT_IN_SLUGS)}),
        *get_skill_bound_tools(),
        *get_generative_tools(),
    ]
    return {t.name: t for t in tools}


@pytest.mark.parametrize("slug", sorted(_EXPECTED_BUILTIN))
def test_builtin_tool_contract_frozen(slug: str) -> None:
    """内置工具的 name / description / args_schema / 同步异步形状一字不变。"""
    expected_desc, expected_async, expected_schema = _EXPECTED_BUILTIN[slug]
    tool = _all_builtin()[slug]
    assert tool.description == expected_desc, f"{slug} 的 description 被改动"
    assert (tool.coroutine is not None) is expected_async, f"{slug} 的同步/异步形状被改动"
    assert _normalized(tool) == expected_schema, f"{slug} 的 args_schema 被改动（LLM 可见，属对外行为）"


def test_platform_tools_are_synchronous() -> None:
    """4 个平台工具必须是同步 ``func``（现状如此，收敛时最易被一律写成 coroutine）。"""
    tools = get_platform_tools()
    assert tools, "平台工具不应为空——否则下面的循环会空跑通过（勘误 3）"
    for tool in tools:
        assert tool.func is not None, f"{tool.name} 应使用同步 func"
        assert tool.coroutine is None, f"{tool.name} 不应被改成异步"


def test_build_platform_tools_gate_matrix() -> None:
    """技能包 / 生成工具两个开关的四种组合，以及**跨组装配顺序**。

    勘误 3：原稿只用集合语义（``<=`` / ``not in``），既锁不住 ``build_platform_tools``
    的拼接顺序（而这正是 Task 2 要重写的那段），也发现不了重复挂载。改为精确有序列表。
    """
    skill = {"skill_package_id": "11111111-1111-1111-1111-111111111111"}
    gen = {"enable_generative_tools": True}

    def names(cfg: dict) -> list[str]:
        return [t.name for t in build_platform_tools(cfg)]

    assert names({}) == ["calculator", "http_request", "get_current_datetime", "knowledge_search"]

    assert names(skill) == [
        "calculator",
        "http_request",
        "get_current_datetime",
        "knowledge_search",
        "skill_read_reference",
        "skill_run_script",
    ]

    assert names(gen) == [
        "calculator",
        "http_request",
        "get_current_datetime",
        "knowledge_search",
        "generate_image",
        "generate_video",
    ]

    # 全组齐开 + 自定义工具 + MCP：完整拼接顺序 = 平台 → opt-in → 技能 → 生成 → 自定义 → MCP
    full = {
        "tool_slugs": list(_OPT_IN_SLUGS),
        **skill,
        **gen,
    }
    assert [t.name for t in build_platform_tools(full, [_CUSTOM_HTTP], [_MCP])] == [
        "calculator",
        "http_request",
        "get_current_datetime",
        "knowledge_search",
        "web_search",
        "code_execution",
        "compliance_check_text",
        "run_flow_once",
        "invoke_tenant_hook",
        "skill_read_reference",
        "skill_run_script",
        "generate_image",
        "generate_video",
        "my_http",
        "mcp__github__create_issue",
    ]


def test_builtin_group_slugs_and_order() -> None:
    """四个分组的成员与**顺序**（顺序即 function schema 顺序，属对外行为）。"""
    assert [t.name for t in get_platform_tools()] == [
        "calculator",
        "http_request",
        "get_current_datetime",
        "knowledge_search",
    ]
    assert [t.name for t in select_opt_in_builtin_tools({"tool_slugs": list(_OPT_IN_SLUGS)})] == list(_OPT_IN_SLUGS)
    assert [t.name for t in get_skill_bound_tools()] == ["skill_read_reference", "skill_run_script"]
    assert [t.name for t in get_generative_tools()] == ["generate_image", "generate_video"]


def test_opt_in_gate_unchanged() -> None:
    """opt-in 工具未勾选不得注入；标量字符串与空配置的语义保持。"""
    assert select_opt_in_builtin_tools({}) == []
    assert select_opt_in_builtin_tools(None) == []
    assert select_opt_in_builtin_tools({"tool_slugs": []}) == []
    assert [t.name for t in select_opt_in_builtin_tools({"tool_slugs": "web_search"})] == ["web_search"]


@pytest.mark.parametrize("slug", sorted(_EXPECTED_SPEC_DRIVEN))
def test_spec_driven_tool_contract_frozen(slug: str) -> None:
    """spec 驱动的 3 类工具（custom http / custom script / mcp）schema 与描述不变。"""
    expected_desc, expected_async, expected_schema = _EXPECTED_SPEC_DRIVEN[slug]
    tool = _spec_driven_tools()[slug]
    assert tool.description == expected_desc
    assert (tool.coroutine is not None) is expected_async
    assert _normalized(tool) == expected_schema
```

- [ ] **Step 2: 核对期望值（已内联，需比对而非填写）**

上表的期望值已由重构前的实现实测导出并内联，**不需要重新生成**。但必须做一次机械核对：

把下列脚本写入 `/tmp/export_tool_contract.py`（**不进仓库**）：

```python
"""导出契约期望值（由重构前的实现产出；仅供一次性填入测试文件）。"""

from __future__ import annotations

import json

from miles_ai.integrations.langchain.tools import (
    CustomToolSpec,
    McpToolSpec,
    build_platform_tools,
    get_generative_tools,
    get_platform_tools,
    get_skill_bound_tools,
    select_opt_in_builtin_tools,
)

_OPT_IN = ("web_search", "code_execution", "compliance_check_text", "run_flow_once", "invoke_tenant_hook")


def _compact(model) -> str:
    return json.dumps(model.model_json_schema(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


for t in [
    *get_platform_tools(),
    *select_opt_in_builtin_tools({"tool_slugs": list(_OPT_IN)}),
    *get_skill_bound_tools(),
    *get_generative_tools(),
]:
    print(f"    {t.name!r}: ({json.dumps(t.description, ensure_ascii=False)}, {t.coroutine is not None}, {_compact(t.args_schema)!r}),")

print()
custom = CustomToolSpec(
    slug="my_http",
    name="My HTTP",
    description="自定义 HTTP 工具",
    tool_type="http",
    parameters=[{"name": "q", "type": "string", "description": "查询词", "required": True}],
)
script = CustomToolSpec(
    slug="my_script",
    name="My Script",
    description=None,
    tool_type="script",
    parameters=[{"name": "n", "type": "integer", "description": "次数", "required": False}],
)
mcp = McpToolSpec(
    slug="mcp__github__create_issue",
    tool_name="create_issue",
    service_id="svc-1",
    service_name="github",
    description="创建 issue",
    input_schema={
        "type": "object",
        "properties": {"title": {"type": "string", "description": "标题"}, "n": {"type": "integer", "default": 3}},
        "required": ["title"],
    },
)
mcp_none = McpToolSpec(
    slug="mcp__svc__nofields",
    tool_name="nofields",
    service_id="svc-1",
    service_name="svc",
    description=None,
    input_schema=None,
)
for key, tools, want in (
    ("custom_http", build_platform_tools({}, [custom]), "my_http"),
    ("custom_script", build_platform_tools({}, [script]), "my_script"),
    ("mcp", build_platform_tools({}, [], [mcp]), "mcp__github__create_issue"),
    ("mcp_none", build_platform_tools({}, [], [mcp_none]), "mcp__svc__nofields"),
):
    t = next(x for x in tools if x.name == want)
    print(f"    {key!r}: ({json.dumps(t.description, ensure_ascii=False)}, {t.coroutine is not None}, {_compact(t.args_schema)!r}),")
```

Run: `uv run --all-packages --group dev python /tmp/export_tool_contract.py`
Expected: 输出 13 行内置 + 4 行 spec 驱动。**逐行与测试文件里已内联的值比对**（`diff` 或肉眼），
不一致说明内联值有误或实现已被改动——两种情况都要先查清再继续。`mcp_none` 一条仅供比对，
不填进 `_EXPECTED_SPEC_DRIVEN`（它对应的是「`input_schema=None` 时由签名反推 schema」这一独立情形）。

> **这是本任务唯一无法靠机器保证的一步**：13 条 description 逐字对照原 `tools.py` 原文。
> 若你发现内联值与实测输出有任何差异，**报告它**，不要静默改测试或改实现。

另外，`_EXPECTED_SPEC_DRIVEN` 的三条需要对应的构造代码，一并加进测试文件：

```python
_CUSTOM_HTTP = CustomToolSpec(
    slug="my_http",
    name="My HTTP",
    description="自定义 HTTP 工具",
    tool_type="http",
    parameters=[{"name": "q", "type": "string", "description": "查询词", "required": True}],
)
_CUSTOM_SCRIPT = CustomToolSpec(
    slug="my_script",
    name="My Script",
    description=None,
    tool_type="script",
    parameters=[{"name": "n", "type": "integer", "description": "次数", "required": False}],
)
_MCP = McpToolSpec(
    slug="mcp__github__create_issue",
    tool_name="create_issue",
    service_id="svc-1",
    service_name="github",
    description="创建 issue",
    input_schema={
        "type": "object",
        "properties": {"title": {"type": "string", "description": "标题"}, "n": {"type": "integer", "default": 3}},
        "required": ["title"],
    },
)
# 勘误 3 新增：input_schema 为 None，make_mcp_tool 省略 args_schema，schema 由占位签名反推。
_MCP_NONE = McpToolSpec(
    slug="mcp__svc__nofields",
    tool_name="nofields",
    service_id="svc-1",
    service_name="svc",
    description=None,
    input_schema=None,
)


def _spec_driven_tools() -> dict:
    """构造 4 类 spec 驱动工具（custom http / custom script / mcp / mcp 无 schema），按 slug 索引。"""
    tools = [
        *build_platform_tools({}, [_CUSTOM_HTTP]),
        *build_platform_tools({}, [_CUSTOM_SCRIPT]),
        *build_platform_tools({}, [], [_MCP]),
        *build_platform_tools({}, [], [_MCP_NONE]),
    ]
    return {
        t.name: t
        for t in tools
        if t.name in {"my_http", "my_script", "mcp__github__create_issue", "mcp__svc__nofields"}
    }
```

> **粘贴后必须人工比对**：把粘贴的每一行与原 `tools.py` 的 description 原文对照。这是本任务唯一无法靠机器保证的一步。

- [ ] **Step 3: 补占位报错文案的断言**

现状**无用例**覆盖「占位必须报错」这条不变量。在测试文件末尾追加（**本步代码已修正，见下方勘误**）：

```python
_STUB_MESSAGE = "请通过 invoke_tool_with_context 执行 {slug}"


def _call_stub(tool) -> None:
    """调用占位函数本体（**不经** ``tool.invoke`` 的 pydantic 校验），让占位报错原样抛出。

    占位有两种签名形状，须分别适配，否则会先抛 ``TypeError`` 而测不到占位报错：

    - ``**kwargs`` 型（``_opt_in_marker`` / ``make_custom_*_tool`` / ``make_mcp_tool``）
      只接受关键字，位置参数会被拒绝；
    - 带具名必填参数的占位（``calculator`` / ``skill_*`` / ``generate_*``）需一个位置
      参数才能进入函数体。
    """
    fn = tool.coroutine if tool.coroutine is not None else tool.func
    accepts_positional = any(
        p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD) for p in inspect.signature(fn).parameters.values()
    )
    args: tuple = ({},) if accepts_positional else ()
    if tool.coroutine is not None:
        asyncio.run(tool.coroutine(*args))
    else:
        fn(*args)


@pytest.mark.parametrize("slug", sorted(_EXPECTED_BUILTIN))
def test_builtin_stub_raises_instead_of_executing(slug: str) -> None:
    """占位壳必须报错，不得静默返回（否则工具会「看起来能执行」）。

    这条不变量原先在 13 个工厂里各抄一遍，任何一处漏写都无人发现——本用例是它的唯一护栏。

    直接调用 ``tool.func`` / ``tool.coroutine``（即占位函数本体），**不经** ``tool.invoke``：
    后者会先过 pydantic 校验，传空参会先抛 ``ValidationError`` 而非占位报错，从而测不到本意。
    实测（重构前）：`calculator.invoke({})` → `ValidationError: Field required`；
    `calculator.func({})` → `RuntimeError: 请通过 invoke_tool_with_context 执行 calculator`。
    """
    tool = _all_builtin()[slug]
    with pytest.raises(RuntimeError, match=_STUB_MESSAGE.format(slug=slug)):
        _call_stub(tool)


@pytest.mark.parametrize("slug", sorted(_EXPECTED_SPEC_DRIVEN))
def test_spec_driven_stub_raises_instead_of_executing(slug: str) -> None:
    tool = _spec_driven_tools()[slug]
    with pytest.raises(RuntimeError, match=_STUB_MESSAGE.format(slug=slug)):
        _call_stub(tool)
```

> **勘误 1（Task 1 实施时实测发现，已回写）**：本步最初的草稿是 `asyncio.run(tool.coroutine({}))`，
> 是**错的**——`_opt_in_marker` 与 `make_mcp_tool` 的占位是 `async def _arun(**kwargs: Any)`，
> **只接受关键字参数**，传位置参数会先抛 `TypeError`（8 条用例必红，与「Step 4 全绿」自相矛盾）。
> 故引入 `_call_stub` 按实际签名适配。**这不是测试放宽**：断言与期望值一字未动，
> 「占位必须抛 `RuntimeError`」的判别力由 Step 5 的证伪实验独立验证。

> **勘误 2（同一轮实测发现，已回写）**：本文件的期望值块是实测导出的长数据（最长一条 1137 字符），
> 超 `line-length = 160` 且会被 formatter 拆行，破坏「每个工具一行、可与导出脚本逐行 diff」的审计性。
> 处置：整文件豁免 `E501`（文件头一行 `# ruff: noqa: E501`），两个数据块以 `# fmt: off` / `# fmt: on`
> 关闭拆行，值为与版式一字未改。**用户已确认采用此形式**（而非移入 `pyproject.toml` 的
> `per-file-ignores`），理由是豁免理由写在数据旁边，读文件即知为何不拆行。

- [ ] **Step 4: 跑测试，必须全绿**

Run: `uv run --all-packages --group dev python -m pytest tests/tenant/tools/test_toolkit_contract.py -q`
Expected: PASS（36 条；`pytest.raises(match=...)` 用 `re.search`，slug 含 `_` 无正则元字符，安全）

> **勘误 3（任务级评审发现，已回写）**：评审指出三处可加固，均在 Task 2 重写
> `build_platform_tools` 之前修掉：
> 1. **跨组装配顺序未被冻结**（Important）。原稿 `test_build_platform_tools_gate_matrix`
>    只用集合语义（`<=` / `not in`），既锁不住 `build_platform_tools:593-616` 的拼接顺序
>    ——而那正是 Task 2 要重写的函数——也发现不了重复挂载；组内顺序虽由
>    `test_builtin_group_slugs_and_order` 覆盖，跨组拼接无人把关。已改为精确有序列表。
> 2. **`input_schema=None` 的 MCP 工具被排除在冻结之外**（少数情形下的唯一漏洞）。
>    `make_mcp_tool` 在该情形下**省略** `args_schema`，schema 由占位签名反推（`title`
>    取工具名）——这是唯一对外 schema 依赖占位签名的工具，也正是 13 个工厂收敛时最易
>    静默改坏的一处。已补 `_MCP_NONE` 与 `mcp__svc__nofields` 契约（见上）。
> 3. `test_platform_tools_are_synchronous` 加非空守卫，避免空列表时空跑通过（见上）。

- [ ] **Step 5: 证伪实验——确认测试真的会红**

三步都要实际执行，不得推理：

1. 临时把 `tools.py` 里 `calculator` 的 `description="安全计算数学表达式"` 改为 `"安全计算数学表达式。"`（加一个句号）：
   Run: `uv run --all-packages --group dev python -m pytest tests/tenant/tools/test_toolkit_contract.py -q`
   Expected: **FAIL**，报 `calculator 的 description 被改动`
2. 还原后，临时把 `_make_calculator_tool` 的 `func=_run` 改成 `coroutine=` 形态（改为 `async def _run` + `coroutine=_run`）：
   Run: 同上 → Expected: **FAIL**，至少 `test_platform_tools_are_synchronous` 与形状断言变红
3. 还原后，临时把 `_make_web_search_tool` 的 `coroutine=_opt_in_marker("web_search")` 换成直接返回 `{"ok": True}` 的假实现：
   Run: 同上 → Expected: **FAIL**，报 `web_search` 未抛 `RuntimeError`

每步之后 `git diff --stat` 确认生产代码已还原干净。

- [ ] **Step 6: 跑全量，确认只增不减**

Run: `uv run --all-packages --group dev python -m pytest -q`
Expected: **>1079 passed**（基线 1079 + 本文件用例数），0 failed

- [ ] **Step 7: Commit**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/.worktrees/langchain-toolkit-split
git add backend/tests/tenant/tools/test_toolkit_contract.py
git commit -F - <<'EOF'
test(toolkit): 冻结工具 schema 契约并补上占位报错断言

拆分 tools.py 与收敛 13 个工厂之前，先用一条特征测试钉住对外可观测面：
16 个工具的 description / args_schema / 同步异步形状 / 分组顺序 / 门控组合。
期望值由当前实现实测导出后内联，非人工手写——13 条 description 有 7 条超 100
字符（最长 199），逐字搬运是本次重构最易出错处。

同时补上「占位必须报错」这条不变量：它原先在 13 个工厂里各抄一遍，任何一处漏写
都会让该工具变成「看起来能执行、实际静默返回」的陷阱，而此前无用例覆盖。
EOF
```

---

### Task 2: 建 `toolkit/` 四个模块并做声明式收敛（`tools.py` 暂作再导出）

**Files:**
- Create: `backend/packages/miles-ai/src/miles_ai/integrations/langchain/toolkit/__init__.py`（空）
- Create: `.../toolkit/naming.py`、`.../toolkit/inputs.py`、`.../toolkit/specs.py`、`.../toolkit/catalog.py`
- Modify: `.../langchain/tools.py` → 降为再导出（下一任务删除）

**Interfaces:**
- Consumes: 无（本任务不依赖 Task 1 的产物，但**必须**在 Task 1 绿之后开始）
- Produces（后续任务与调用点依赖这些**精确**签名）：
  - `toolkit.naming`：`MCP_FUNCTION_PREFIX: str`、`sanitize_ident(raw: str) -> str`、`compose_mcp_tool_name(service_name: str, tool_name: str) -> str`、`is_mcp_tool_name(name: str | None) -> bool`、`select_agent_tools(tools: list, allowed_slugs: list | None, *, always_allow: set[str] | None = None) -> list`
  - `toolkit.inputs`：13 个 `BaseModel`（`CalculatorInput`、`HttpRequestInput`、`KnowledgeSearchInput`、`GenerateImageInput`、`GenerateVideoInput`、`DateTimeInput`、`SkillReadReferenceInput`、`SkillRunScriptInput`、`WebSearchInput`、`CodeExecutionInput`、`ComplianceCheckTextInput`、`RunFlowOnceInput`、`InvokeTenantHookInput`）
  - `toolkit.specs`：`CustomToolSpec`、`McpToolSpec`、`mcp_param_alias(input_schema: dict | None) -> dict[str, str]`、`json_schema_to_pydantic(input_schema: dict | None, *, model_name: str = "McpToolParams") -> type[BaseModel] | None`
  - `toolkit.catalog`：`build_stub_tool(slug: str, description: str, args_schema: type[BaseModel] | None, *, is_async: bool) -> StructuredTool`、`make_builtin_tool(slug: str) -> StructuredTool`、`get_platform_tools()`、`select_opt_in_builtin_tools(agent_config: dict | None)`、`get_skill_bound_tools()`、`get_generative_tools()`、`make_custom_http_tool(spec)`、`make_custom_script_tool(spec)`、`make_mcp_tool(spec)`、`build_platform_tools(agent_config, custom_specs=None, mcp_specs=None)`

> **本任务的收敛范围**：13 个静态工厂 → 声明表 + 构造器。`build_stub_tool` 的占位签名**必须**是 `**kwargs: Any`——实测：`make_mcp_tool` 在 `input_schema=None` 时 `args_schema` 缺省，LangChain 会**从占位函数签名反推 schema**（`title` 取工具名）。占位签名一变，该情形的对外 schema 会静默改变（Task 1 的导出脚本里 `mcp_none` 一条即为盯住它）。
>
> 已核实现状（Task 1 实施时读码确认）：`make_mcp_tool:580` 与 `_opt_in_marker:300` 的占位本就是
> `async def _arun(**kwargs: Any)`，故上述情形在本任务中**签名不变、schema 不变**；
> 真正会被统一改动的是 `calculator` / `skill_*` / `generate_*` 等**带具名参数**的占位，
> 而它们的 `args_schema` 均为显式传入——独立 probe 已实测「具名签名 → `**kwargs`」在显式
> `args_schema` 下产出**逐字节相同**的 `StructuredTool` schema。Task 1 的 15 条异步契约断言
> 会在本任务后继续把这条钉住。

- [ ] **Step 1: 建空 `__init__.py`**

```bash
mkdir -p backend/packages/miles-ai/src/miles_ai/integrations/langchain/toolkit
touch backend/packages/miles-ai/src/miles_ai/integrations/langchain/toolkit/__init__.py
```

文件**必须为空**（0 字节）。不得写 `__all__`、不得再导出——本设计刻意不留转发壳。

- [ ] **Step 2: 建 `naming.py`（自 `tools.py:33-98` 搬迁）**

把 `tools.py:33-98` 的 MCP 命名区与 `select_agent_tools` **原样**移入（逐字，不改任何 docstring 与逻辑），文件头为：

```python
"""MCP 工具的 LLM function name 约定，与按 name 的工具白名单过滤。

纯字符串 / 名称语义，无 DB、无 LangChain 依赖。被 portal 的 MCP 装配与执行分发复用。
"""

from __future__ import annotations

import hashlib
import re

# --- MCP 工具 → LLM function name（OpenAI 仅允许 [A-Za-z0-9_-]，≤64 字符）---

MCP_FUNCTION_PREFIX = "mcp__"
_MAX_FUNCTION_NAME = 64
_INVALID_IDENT_CHARS = re.compile(r"[^A-Za-z0-9_]")

# <此后原样粘贴 tools.py:43-98 的 sanitize_ident / _service_ident /
#  compose_mcp_tool_name / is_mcp_tool_name / select_agent_tools，含全部 docstring 与注释>
```

- [ ] **Step 3: 建 `inputs.py`（自 `tools.py:189-297` 搬迁）**

把 13 个 DTO **原样**移入，文件头为：

```python
"""内置工具 / 技能 / 生成类工具的入参 schema（纯声明，仅 LLM 可见）。

仅供 ``StructuredTool`` 的 ``args_schema`` 使用；执行不经这些模型。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# <此后原样粘贴 tools.py:189-297 的 13 个 BaseModel，含每个类上方的 ``#`` 说明注释>
```

- [ ] **Step 4: 建 `specs.py`（自 `tools.py:39,100-188` 搬迁）**

把两个 spec 与 JSON Schema 转换器**原样**移入（含 `_INVALID_FIELD_CHARS` 常量，它此前定义在 `tools.py:40`）：

```python
"""租户自定义工具 / MCP 工具的中性 spec，以及 JSON Schema → pydantic 的转换。

中性 spec 由 L1 loader 自 ORM 构造；转换器仅生成 LLM 可见的 parameters schema，执行不经它。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, create_model

_INVALID_FIELD_CHARS = re.compile(r"\W")

# <此后原样粘贴 tools.py:100-121（CustomToolSpec / McpToolSpec）与
#  tools.py:123-188（_field_name / mcp_param_alias / json_schema_to_pydantic / _json_scalar_type）>
```

- [ ] **Step 5: 建 `catalog.py` 并做声明式收敛**

```python
"""内置工具的声明式注册表与 ``StructuredTool`` 构造（纯 schema 构造，无 DB、无执行）。

职责
----
- ``_DECLS`` 声明每个内置工具的 description / args_schema / 同步异步形状；
  ``build_stub_tool`` 是**唯一**的构造路径，占位报错文案与 func/coroutine 二选一只存于它一处。
- 本模块的 ``func`` / ``_arun`` 均为占位——主循环从不直接执行 ``StructuredTool``，
  实际执行统一走 L1 ``invoke_tool_with_context``（含确认与审计），误调用即抛错提示。
- 分组视图（平台 / opt-in / 技能 / 生成）与 ``build_platform_tools`` 的总装配。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from miles_core.models.tool.parameters import parameters_to_pydantic

from .inputs import (
    CalculatorInput,
    CodeExecutionInput,
    ComplianceCheckTextInput,
    DateTimeInput,
    GenerateImageInput,
    GenerateVideoInput,
    HttpRequestInput,
    InvokeTenantHookInput,
    KnowledgeSearchInput,
    RunFlowOnceInput,
    SkillReadReferenceInput,
    SkillRunScriptInput,
    WebSearchInput,
)
from .specs import CustomToolSpec, McpToolSpec, json_schema_to_pydantic

__all__ = [
    "CustomToolSpec",
    "McpToolSpec",
    "build_platform_tools",
    "build_stub_tool",
    "get_generative_tools",
    "get_platform_tools",
    "get_skill_bound_tools",
    "make_builtin_tool",
    "make_custom_http_tool",
    "make_custom_script_tool",
    "make_mcp_tool",
    "select_opt_in_builtin_tools",
]


@dataclass(frozen=True)
class ToolDecl:
    """一个内置工具的声明（slug 由声明表的键承载，避免重复书写）。"""

    description: str
    args_schema: type[BaseModel]
    is_async: bool = True


def build_stub_tool(
    slug: str,
    description: str,
    args_schema: type[BaseModel] | None,
    *,
    is_async: bool,
) -> StructuredTool:
    """构造占位 ``StructuredTool``：schema 供 LLM 选型，执行一律走 L1。

    占位体统一报错（避免被当作可执行工具直接调用）；``is_async`` 决定用 ``func`` 还是
    ``coroutine``——这不是风格差异，``StructuredTool`` 据此决定哪个属性非空，误写会静默
    改变工具的调用形态。

    ``args_schema=None`` 时**不传**该 kwarg（与现状一致）：此时 LangChain 从占位签名
    ``(**kwargs)`` 反推 schema、``title`` 取工具名，故占位签名不得改动。
    """
    message = f"请通过 invoke_tool_with_context 执行 {slug}"

    if is_async:

        async def _arun(**kwargs: Any) -> dict:
            raise RuntimeError(message)

        placeholder: dict[str, Any] = {"coroutine": _arun}
    else:

        def _run(**kwargs: Any) -> dict:
            raise RuntimeError(message)

        placeholder = {"func": _run}

    kwargs: dict[str, Any] = {"name": slug, "description": description, **placeholder}
    if args_schema is not None:
        kwargs["args_schema"] = args_schema
    return StructuredTool.from_function(**kwargs)


# --- 声明表：新增内置工具 = 加一行 -------------------------------------------------

_PLATFORM_SLUGS: tuple[str, ...] = ("calculator", "http_request", "get_current_datetime", "knowledge_search")
_OPT_IN_SLUGS: tuple[str, ...] = ("web_search", "code_execution", "compliance_check_text", "run_flow_once", "invoke_tenant_hook")
_SKILL_SLUGS: tuple[str, ...] = ("skill_read_reference", "skill_run_script")
_GENERATIVE_SLUGS: tuple[str, ...] = ("generate_image", "generate_video")

_DECLS: dict[str, ToolDecl] = {
    # 平台内置：恒在，且现状为**同步** func
    "calculator": ToolDecl("安全计算数学表达式", CalculatorInput, is_async=False),
    "http_request": ToolDecl("发起 HTTP 请求", HttpRequestInput, is_async=False),
    "get_current_datetime": ToolDecl("获取当前的日期时间", DateTimeInput, is_async=False),
    "knowledge_search": ToolDecl("在指定知识库中语义检索", KnowledgeSearchInput, is_async=False),
    # L2 opt-in：须在 agent.config.tool_slugs 显式勾选
    "web_search": ToolDecl("使用 DuckDuckGo 搜索网页，返回摘要与相关链接", WebSearchInput),
    "code_execution": ToolDecl("在 Runner 沙箱中执行 Python 代码片段（须符合安全校验）", CodeExecutionInput),
    "compliance_check_text": ToolDecl("检测文本是否命中租户敏感词库，返回命中词与 warn/block 处置建议（只读）", ComplianceCheckTextInput),
    "run_flow_once": ToolDecl("执行本租户一个已发布流程一次并返回其输出；仅限已发布流程，执行前需用户确认", RunFlowOnceInput),
    "invoke_tenant_hook": ToolDecl("手动触发本租户已绑定的 HTTP 钩子（按触发时机与作用域），返回各钩子状态与改写后的载荷", InvokeTenantHookInput),
    # 技能包绑定 / 生成开关
    "skill_read_reference": ToolDecl("读取绑定技能包 references/ 或 assets/ 下的文本文件", SkillReadReferenceInput),
    "skill_run_script": ToolDecl("在沙箱中执行绑定技能包 scripts/ 下的 Python 脚本", SkillRunScriptInput),
    "generate_image": ToolDecl(
        "生成图片（文生图/图生图）。直接通过 function calling 调用，传入 prompt 等参数即可，禁止在文字中描述调用过程。",
        GenerateImageInput,
    ),
    "generate_video": ToolDecl(
        "生成短视频（文/图生视频）。直接通过 function calling 调用，传入 prompt 等参数即可，禁止在文字中描述调用过程。耗时长，异步排队。",
        GenerateVideoInput,
    ),
}


def _build(slug: str) -> StructuredTool:
    decl = _DECLS[slug]
    return build_stub_tool(slug, decl.description, decl.args_schema, is_async=decl.is_async)


def _tools_for(slugs: Sequence[str]) -> list[StructuredTool]:
    return [_build(s) for s in slugs]


def make_builtin_tool(slug: str) -> StructuredTool:
    """按 slug 取单个内置工具 schema 壳；未知 slug 抛 ``KeyError``（无「返回 None」语义）。"""
    return _build(slug)


def get_platform_tools() -> list[StructuredTool]:
    """返回内置工具列表（纯 schema 壳，无 DB/租户参数）。"""
    return _tools_for(_PLATFORM_SLUGS)


def get_skill_bound_tools() -> list[StructuredTool]:
    """Agent 绑定 ``skill_package_id`` 时追加的技能工具对。"""
    return _tools_for(_SKILL_SLUGS)


def get_generative_tools() -> list[StructuredTool]:
    """由 ``build_platform_tools`` 在 ``agent.config.enable_generative_tools`` 时挂载。"""
    return _tools_for(_GENERATIVE_SLUGS)


def select_opt_in_builtin_tools(agent_config: dict | None) -> list[StructuredTool]:
    """按 ``config.tool_slugs`` 白名单返回 L2 opt-in 内置工具 schema（未勾选不注入）。

    这些工具默认不进入 function schema：外呼/执行类能力须由租户在智能体「能力」
    中显式勾选，避免 ``tool_slugs`` 为空（= 全部）时被默认放开。
    """
    cfg = agent_config if isinstance(agent_config, dict) else {}
    raw = cfg.get("tool_slugs") or []
    if isinstance(raw, str):
        raw = [raw]
    wanted = {str(s) for s in raw if s}
    return _tools_for([s for s in _OPT_IN_SLUGS if s in wanted])


def make_custom_http_tool(spec: CustomToolSpec) -> StructuredTool:
    """将租户 HTTP 工具（``CustomToolSpec``）转为 StructuredTool（schema 供 LLM；执行走 invoke）。"""
    return build_stub_tool(spec.slug, spec.description or spec.name, parameters_to_pydantic(spec.parameters), is_async=True)


def make_custom_script_tool(spec: CustomToolSpec) -> StructuredTool:
    """将租户 Python 脚本工具（``CustomToolSpec``）转为 StructuredTool（schema 供 LLM；执行走 invoke）。"""
    return build_stub_tool(spec.slug, spec.description or spec.name, parameters_to_pydantic(spec.parameters), is_async=True)


def make_mcp_tool(spec: McpToolSpec) -> StructuredTool:
    """将绑定 MCP 的单个 tool（``McpToolSpec``）转为 StructuredTool。

    schema 取自 ``inputSchema``（JSON Schema → pydantic），仅供 LLM 选型填参；
    实际执行走 L1 ``invoke_tool_with_context``（``source=mcp``）。
    """
    return build_stub_tool(
        spec.slug,
        spec.description or f"{spec.service_name} · {spec.tool_name}",
        json_schema_to_pydantic(spec.input_schema),
        is_async=True,
    )


def build_platform_tools(
    agent_config: dict | None,
    custom_specs: list[CustomToolSpec] | None = None,
    mcp_specs: list[McpToolSpec] | None = None,
) -> list[StructuredTool]:
    """构造画布/对话工具 schema 列表（纯函数，不查 DB、不执行）。

    内置工具 + 绑定技能包 ``skill_*`` + ``enable_generative_tools`` 时的
    ``generate_*`` + 租户自定义 HTTP/SCRIPT 工具 + 绑定 MCP 服务的 tools。
    ``agent_config`` 缺失时仅内置工具。
    """
    cfg = agent_config if isinstance(agent_config, dict) else {}
    tools = [*get_platform_tools(), *select_opt_in_builtin_tools(cfg)]
    if cfg.get("skill_package_id"):
        tools = [*tools, *get_skill_bound_tools()]
    if cfg.get("enable_generative_tools"):
        tools = [*tools, *get_generative_tools()]
    for spec in custom_specs or []:
        if spec.tool_type == "http":
            tools.append(make_custom_http_tool(spec))
        elif spec.tool_type == "script":
            tools.append(make_custom_script_tool(spec))
    for spec in mcp_specs or []:
        tools.append(make_mcp_tool(spec))
    return tools
```

> **逐字核对点**（`_DECLS` 的 description 必须与 `tools.py` 原文一字不差）：13 条中 7 条超 100 字符。
> 若 Task 1 的契约测试在你写完 `catalog.py` 后仍全绿，说明抄写正确——这正是 Task 1 先行的意义。

- [ ] **Step 6: `tools.py` 降为再导出，跑测试确认全绿**

把 `tools.py` 整个文件替换为（**临时**再导出，Task 3 删除；这样 1079 条既有测试继续有效，本任务的 diff 可作纯搬迁审阅）：

```python
"""**临时**再导出层：``toolkit/`` 拆分期间保持既有 import 路径可用，随 Task 3 一并删除。

本模块不得新增任何逻辑；所有符号归属见同目录 ``toolkit/`` 各模块。
"""

from __future__ import annotations

from .toolkit.catalog import (
    build_platform_tools,
    build_stub_tool,
    get_generative_tools,
    get_platform_tools,
    get_skill_bound_tools,
    make_builtin_tool,
    make_custom_http_tool,
    make_custom_script_tool,
    make_mcp_tool,
    select_opt_in_builtin_tools,
)
from .toolkit.naming import (
    MCP_FUNCTION_PREFIX,
    compose_mcp_tool_name,
    is_mcp_tool_name,
    sanitize_ident,
    select_agent_tools,
)
from .toolkit.specs import CustomToolSpec, McpToolSpec, json_schema_to_pydantic, mcp_param_alias

# 转发壳自身不使用这些 import：非 ``__init__`` 模块的裸转发会被 F401 全部报出，
# 与「是否有调用点」无关（F401 只看本文件）。故显式声明再导出面。
__all__ = [
    "MCP_FUNCTION_PREFIX",
    "CustomToolSpec",
    "McpToolSpec",
    "build_platform_tools",
    "build_stub_tool",
    "compose_mcp_tool_name",
    "get_generative_tools",
    "get_platform_tools",
    "get_skill_bound_tools",
    "is_mcp_tool_name",
    "json_schema_to_pydantic",
    "make_builtin_tool",
    "make_custom_http_tool",
    "make_custom_script_tool",
    "make_mcp_tool",
    "mcp_param_alias",
    "sanitize_ident",
    "select_agent_tools",
    "select_opt_in_builtin_tools",
]
```

> 这份清单是**实测**出来的（`rg` 扫过全部调用点），不是照抄原文件：13 个静态工厂与
> `_opt_in_marker` 均**不**在此列——它们被声明表取代。`make_knowledge_search_tool` 同样不在列，
> 但其唯一消费者（`tests/tenant/tools/test_knowledge_search_coexistence.py`）需要在本步一并改掉，
> 见 Step 7。没有调用点从本模块导入 13 个 DTO，故此处**不做** `import *`。

- [ ] **Step 7: 迁移 `make_knowledge_search_tool` 的唯一消费者**

`tests/tenant/tools/test_knowledge_search_coexistence.py` 是 `make_knowledge_search_tool` 在全仓的唯一消费者
（实测；生产代码无引用）。工厂收敛后该符号消失，等价替换为 `make_builtin_tool("knowledge_search")`：

- 第 13-17 行的 import：删去 `make_knowledge_search_tool`，加入 `make_builtin_tool`
- 第 166 行：`schema = make_knowledge_search_tool().args_schema.model_json_schema()`
  → `schema = make_builtin_tool("knowledge_search").args_schema.model_json_schema()`

Run: `uv run --all-packages --group dev python -m pytest tests/tenant/tools/test_knowledge_search_coexistence.py -q`
Expected: PASS

- [ ] **Step 8: 跑测试确认全绿**

Run: `uv run --all-packages --group dev python -m pytest tests/tenant/tools/test_toolkit_contract.py -q`
Expected: PASS（契约全绿 ⇒ 声明式收敛未改变对外行为）

Run: `uv run --all-packages --group dev python -m pytest -q`
Expected: **与 Task 1 结束时相同的通过数**，0 failed

- [ ] **Step 9: 五道门禁**

依次执行 Global Constraints 里的 5 条命令。
Expected: 全部通过。

> **勘误 5（Task 2 实施时实测发现，已回写）**：本步原稿写「若 `ruff check` 报 `F401`，
> 按实测清单删掉该符号，**不要**加 `# noqa`」——**这两句都是错的**。
> `tools.py` 不是 `__init__.py`，其裸转发导入会被 F401 **全部**报出，与「有没有调用点」无关
> （F401 只看本文件；实测：`build_platform_tools`、`get_platform_tools`、`McpToolSpec`
> 三个确有调用点的符号一并被报）。按「删掉 F401 符号」执行会删空整个壳、1079 条测试全红。
> 正解是在壳里显式声明 `__all__`（已补入 Step 6 的代码块）：无需抑制、语义化声明再导出面，
> 且符合本步「不加 `# noqa`」的原意。
> 仓库另有一处同类临时 shim（`miles_portal/tenant/tools/parameters.py:6`）用模块级
> `# noqa: F401`，是可行替代；此处选 `__all__` 因为它不需要抑制、表达力更强，
> 且该壳本身在 Task 3 即被删除。

- [ ] **Step 10: Commit**

```bash
git add backend/packages/miles-ai/src/miles_ai/integrations/langchain/ backend/tests/tenant/tools/test_knowledge_search_coexistence.py
git commit -F - <<'EOF'
refactor(toolkit): 拆出 naming/inputs/specs 并把工具工厂收敛为声明表

tools.py 617 行承担 6 类职责，且 13 个工具工厂是同一段代码抄 13 遍——「占位必须
报错、执行一律走 L1」是本模块唯一的实质不变量，却重复了 13 份。按职责拆为 toolkit/
四模块，工厂收敛为「声明表 + 单一构造器」：报错文案与 func/coroutine 二选一各只存
一处，新增内置工具从「改 3 处」变成「加一行」。

同步/异步形态按现状保留（4 个平台工具是同步 func，非风格差异，StructuredTool 据此
决定哪个属性非空）。占位签名保持 **kwargs——make_mcp_tool 在 input_schema 为 None 时
由 LangChain 从签名反推 schema，签名一变对外 schema 会静默改变。

tools.py 暂降为再导出层（符号清单由调用点实测得出，非照抄原文件），使既有 1079 条
测试在本次搬迁中继续有效；随下一提交删除。make_knowledge_search_tool 的唯一消费者
（测试）等价改用 make_builtin_tool("knowledge_search")。
EOF
```

---

### Task 3: 删除 `tools.py`、迁移 11 处调用点、收口

**Files:**
- Delete: `backend/packages/miles-ai/src/miles_ai/integrations/langchain/tools.py`
- Modify: 生产 7 处 + 测试 5 处（含 Task 1 新增的契约测试）
- Modify: `backend/packages/miles-core/src/miles_core/models/tool/__init__.py:4`（docstring）

**Interfaces:**
- Consumes: Task 2 产出的 `toolkit.{naming,inputs,specs,catalog}` 全部符号
- Produces: 最终状态——`rg "langchain\.tools"` 零命中

> **本任务是纯机械迁移**：漏改的失败模式是导入期 `ImportError`（响亮、即时），不是静默降级。
> 这正是「不留转发壳」的前提条件。

- [ ] **Step 1: 迁移生产 7 处**

逐处改 import，不改任何其他代码：

1. `backend/packages/miles-portal/src/miles_portal/tenant/tools/services/mcp_tools.py:22-27`
   ```python
   from miles_ai.integrations.langchain.toolkit.naming import compose_mcp_tool_name, is_mcp_tool_name
   from miles_ai.integrations.langchain.toolkit.specs import McpToolSpec, mcp_param_alias
   ```
2. `backend/packages/miles-portal/src/miles_portal/tenant/tools/services/custom_tools.py:14`
   ```python
   from miles_ai.integrations.langchain.toolkit.catalog import build_platform_tools
   from miles_ai.integrations.langchain.toolkit.specs import CustomToolSpec
   ```
3. `backend/packages/miles-portal/src/miles_portal/tenant/tools/services/tools.py:21`
   ```python
   from miles_ai.integrations.langchain.toolkit.naming import is_mcp_tool_name
   ```
4. `backend/packages/miles-portal/src/miles_portal/tenant/tools/confirmation.py:8`
   ```python
   from miles_ai.integrations.langchain.toolkit.naming import is_mcp_tool_name
   ```
5. `backend/packages/miles-portal/src/miles_portal/tenant/tools/invoke/context.py:12`
   ```python
   from miles_ai.integrations.langchain.toolkit.naming import is_mcp_tool_name
   ```
6. `backend/packages/miles-portal/src/miles_portal/tenant/agents/services/context.py:15`
   ```python
   from miles_ai.integrations.langchain.toolkit.naming import compose_mcp_tool_name
   ```
7. `backend/packages/miles-ai/src/miles_ai/integrations/langchain/tool_agent/loop.py:19`
   ```python
   from miles_ai.integrations.langchain.toolkit.catalog import get_skill_bound_tools
   from miles_ai.integrations.langchain.toolkit.naming import select_agent_tools
   ```

- [ ] **Step 2: 迁移测试 5 处**

8. `backend/tests/mcp/test_mcp_function_calling.py:11-20`
   ```python
   from miles_ai.integrations.langchain.toolkit.catalog import build_platform_tools
   from miles_ai.integrations.langchain.toolkit.naming import (
       MCP_FUNCTION_PREFIX,
       compose_mcp_tool_name,
       is_mcp_tool_name,
       select_agent_tools,
   )
   from miles_ai.integrations.langchain.toolkit.specs import McpToolSpec, json_schema_to_pydantic, mcp_param_alias
   ```
9. `backend/tests/tenant/tools/test_builtin_opt_in.py:5-9`
   ```python
   from miles_ai.integrations.langchain.toolkit.catalog import (
       build_platform_tools,
       get_platform_tools,
       select_opt_in_builtin_tools,
   )
   ```
10. `backend/tests/tenant/tools/test_knowledge_search_coexistence.py:13-17`——注意 `select_agent_tools` 归 `naming`
    （`make_builtin_tool` 的替换已在 Task 2 Step 7 完成，此处**只改模块路径**）：
    ```python
    from miles_ai.integrations.langchain.toolkit.catalog import get_platform_tools, make_builtin_tool
    from miles_ai.integrations.langchain.toolkit.naming import select_agent_tools
    ```
    **并把过时的测试函数名改掉**（Task 2 评审 Minor）：该文件 `:165` 的
    `test_make_knowledge_search_tool_schema_allows_kb_ids` 里的符号已不存在，改名如
    `test_knowledge_search_tool_schema_allows_kb_ids`。改名会改测试节点 id，属预期，
    不改断言。
11. `backend/tests/tenant/skills/test_skill_runtime_integration.py:7`
    ```python
    from miles_ai.integrations.langchain.toolkit import catalog as lc_tools
    ```
12. `backend/tests/tenant/tools/test_toolkit_contract.py`（Task 1 新建）
    ```python
    from miles_ai.integrations.langchain.toolkit.catalog import (
        build_platform_tools,
        get_generative_tools,
        get_platform_tools,
        get_skill_bound_tools,
        select_opt_in_builtin_tools,
    )
    from miles_ai.integrations.langchain.toolkit.specs import CustomToolSpec, McpToolSpec
    ```
    > 本文件其余内容**一字不改**——期望值不变，是它作为契约的意义所在。
    >
    > **唯一例外**：`_call_stub` 里「按签名适配」的分支须在此简化掉。Task 2 已把全部占位
    > 统一为 `**kwargs`，`accepts_positional` 恒为 False，那个分支成了死代码。改成直接调用：
    > ```python
    > def _call_stub(tool) -> None:
    >     """调用占位函数本体（**不经** ``tool.invoke`` 的 pydantic 校验），让占位报错原样抛出。
    >
    >     占位统一为 ``**kwargs``，无位置参数可传；这也正是 ``tool.invoke({})`` 测不到本意
    >     （会先抛 pydantic ``ValidationError``）的原因。
    >     """
    >     if tool.coroutine is not None:
    >         asyncio.run(tool.coroutine())
    >     else:
    >         tool.func()
    > ```
    > 随之删掉不再使用的 `import inspect`（否则 ruff `F401` 会拦住门禁）。
    > 期望值与断言仍**一字不改**。
    >
    > **同时补一条断言**（任务级评审建议）：占位统一为 `**kwargs` 后，
    > 「占位不接受位置参数」应成为**显式期望**而非 `_call_stub` 默默适配的结果——
    > 否则将来某个占位悄悄带着位置参数，测试仍会通过。在 `test_builtin_stub_raises_instead_of_executing`
    > 内加：
    > ```python
    >     fn = tool.coroutine if tool.coroutine is not None else tool.func
    >     positional = [
    >         p
    >         for p in inspect.signature(fn).parameters.values()
    >         if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
    >     ]
    >     assert not positional, f"{slug} 的占位不应接受位置参数（统一为 **kwargs）"
    > ```
    > 注意：**这一条会重新需要 `import inspect`**。故顺序是——先把 `_call_stub` 简化掉、
    > 保留 `import inspect` 供本断言使用（不要删），再补此断言。`ruff check` 会因
    > `inspect` 仍被使用而放行。

- [ ] **Step 3: 删除 `tools.py`**

```bash
git rm backend/packages/miles-ai/src/miles_ai/integrations/langchain/tools.py
```

- [ ] **Step 4: 同步 docstring / 注释里的旧路径**

**勘误 6（Task 3 实施后发现，已修正本步的搜索方式）**：本步原稿只用
`rg -n "langchain\.tools"`（点号形式）验证，**不足以**证明「没有旧路径残留」——
斜杠形式 `langchain/tools`、以及不带包名前缀的 `toolkit 旧路径` 都不会命中。
实测漏掉的引用（Task 3 已修其中 2 处，其余由修复轮处理）：

| 位置 | 形式 | 处置 |
|---|---|---|
| `miles_core/models/tool/__init__.py:4` | 点号 | Task 3 已改 |
| `miles_portal/.../tools/services/mcp_tools.py:12` | 点号 | Task 3 已改 |
| `miles_core/models/tool/parameters.py:1` | 斜杠 | 修复轮改 |
| `miles_portal/.../tools/services/custom_tools.py:5` | 斜杠（历史叙述） | 修复轮改 |
| `docs/guides/ai-stack.md:76` | 斜杠（**可执行的开发指南**） | 修复轮改 |
| `docs/architecture/tools-runtime.md:171` | 斜杠（架构图） | 修复轮改 |
| `docs/architecture/tools-runtime.md:360` | 斜杠（路径表） | 修复轮改 |

搜索必须覆盖两种形式：

```bash
rg -n "langchain[./]tools" backend/packages backend/tests docs
```

Expected: 仅命中**描述本次重构本身**的历史文档（`docs/superpowers/specs/2026-09-16-*`
与 `docs/superpowers/plans/2026-09-16-*`），这些提到旧路径是在讲「做了什么」，属正确；其余零命中。

- [ ] **Step 5: 跑测试与门禁**

Run: `uv run --all-packages --group dev python -m pytest tests/tenant/tools/test_toolkit_contract.py tests/mcp/test_mcp_function_calling.py tests/tenant/tools/test_builtin_opt_in.py tests/tenant/tools/test_knowledge_search_coexistence.py tests/tenant/skills/test_skill_runtime_integration.py -q`
Expected: PASS，期望值与 Task 1 结束时**完全相同**（契约文件一字未改）

依次执行 Global Constraints 的 5 条门禁。
Expected: 全部通过；测试数与 Task 2 结束时相同。

- [ ] **Step 6: Commit**

```bash
git add -A backend/packages backend/tests
git commit -F - <<'EOF'
refactor(toolkit): 删除 tools.py 并将 11 处调用点按职责迁移

拆分完成后 tools.py 只剩再导出，留着即两条「同一件事的入口」，故删除；调用点按
职责直接 import（naming 名称语义 / specs 中性 spec 与 schema 转换 / catalog 装配）。
三处仅用 is_mcp_tool_name 的站点只依赖 naming，不再牵入整个装配模块。

漏改的失败模式是导入期 ImportError，响亮且即时，故不留转发壳是安全的。同步更新
miles_core 里指向旧路径的 docstring；tests/tenant/tools/test_toolkit_contract.py
的期望值一字未改，作为「行为不变」的凭据。
EOF
```

---

### Task 4: 终检（独立复核，不写新代码）

**Files:**
- Modify: 仅当发现缺陷时；否则无改动

**Interfaces:**
- Consumes: Task 1-3 的全部产物
- Produces: 复核结论

- [ ] **Step 1: 五道门禁全量重跑**

依次执行 Global Constraints 的 5 条命令，记录原始输出。
Expected: 全绿。特别注意 `export_openapi --check`——13 个 DTO 的 description 会进 function schema，若被改动快照会响。

- [ ] **Step 2: 记录测试计数**

Run: `uv run --all-packages --group dev python -m pytest -q | tail -3`
Expected: `>1079 passed`，0 failed，无 warnings summary（与基线同）。若数字与 Task 1 记录不符，**调查原因并报告**，不得直接接受。

- [ ] **Step 3: 独立证伪——确认契约测试仍具判别力（在最终代码上重做一次）**

1. 在 `catalog.py` 里把 `generate_video` 的 description 末尾句号删掉：
   Run: `uv run --all-packages --group dev python -m pytest tests/tenant/tools/test_toolkit_contract.py -q`
   Expected: **FAIL**，报 `generate_video 的 description 被改动`
2. 还原后，把 `"calculator"` 声明的 `is_async=False` 删掉（落回默认 `True`）：
   Run: 同上 → Expected: **FAIL**（`test_platform_tools_are_synchronous` + 契约形状断言）
3. 还原后，让 `build_stub_tool` 的异步占位改为 `return {}`（不报错）：
   Run: 同上 → Expected: **FAIL**，报 `web_search`（等）未抛 `RuntimeError`
4. 每步还原后 `git status --porcelain` 必须为空。

- [ ] **Step 4: 确认非目标未被触碰**

Run: `git diff --stat main...HEAD -- backend/packages/miles-portal`
Expected: 仅 6 个文件的 **import 行**改动（`mcp_tools.py` / `custom_tools.py` / `services/tools.py` / `confirmation.py` / `invoke/context.py` / `agents/services/context.py`），无逻辑改动。

Run: `rg -n "short_db_session|get_worker_session" backend/packages` → Expected: 零命中（与本任务无关，确认没有回退破坏）

- [ ] **Step 5: 更新 spec 的修订记录**

在 `docs/superpowers/specs/2026-09-16-langchain-toolkit-split-design.md` §10 追加一条实施记录（实测计数、遇到的偏差、与设计的任何出入）。若有与设计不符之处，同时修正正文对应章节。

- [ ] **Step 6: Commit**

```bash
git add -A docs
git commit -F - <<'EOF'
docs(spec): 记录 toolkit 拆分的实施结果

补记实测测试计数、契约测试的证伪结论，以及与设计的任何出入。
EOF
```

---

## 自检记录

| 检查 | 结果 |
|---|---|
| **Spec 覆盖** | §1 问题→Task 2/3；§3 目标 1-4→Task 2（4 模块 + 收敛）与 Task 3（按职责 import）；§4 非目标→Task 4 Step 4 核验；§5.1-5.4→Task 2/3；§7.1 全 5 条→Task 1；§7.2→Task 3 Step 5 与 Task 4；§8 R1-R7→Task 1（R1/R2 断言）、Task 3 Step 4（R4/R5）、门禁 `lint-imports`（R6） |
| **占位扫描** | 无「TBD/TODO/补充测试」；Task 1 的期望值已**完整内联**（13 + 3 条），Step 2 只做比对不做填写——这是唯一无法机器保证的一步，已显式标注 |
| **类型一致性** | `build_stub_tool(slug, description, args_schema, *, is_async)` 在 Task 2 定义、Task 4 复用于证伪；`make_builtin_tool(slug)` 在 Task 2 定义、Task 3 Step 2 第 10 项使用；`ToolDecl(description, args_schema, is_async=True)` 与 `_DECLS` 全部 13 条一致 |
| **测试代码已实测** | Task 1 Step 3 的占位报错断言经两轮实测修正（见该步的两条勘误）：`tool.invoke({})` 会先抛 `ValidationError`（pydantic 必填校验），测不到占位体；而 `tool.coroutine({})` 对 `_opt_in_marker` / `make_mcp_tool` 的 `**kwargs` 型占位会先抛 `TypeError`（实测该类占位只收关键字）。最终以 `_call_stub` 按签名适配，断言与期望值未动，判别力由 Step 5 证伪实验独立验证 |
| **lint 豁免已定** | 期望值行最长 1137 字符，超 `line-length = 160`；用户确认采用文件级 `# ruff: noqa: E501` + 数据块 `# fmt: off`（理由就近写在数据旁），不迁入 `pyproject.toml` 的 `per-file-ignores` |
| **导入已实测** | 勘误 4：`catalog.py` 原稿写 `from typing import Any, Sequence`，实测触发 `UP035`（该规则在 `select` 列表内且未豁免）→ 已改为 `from collections.abc import Sequence` + `from typing import Any`。Task 2 若照原稿写会直接卡在 `ruff check` |
| **F401 判断已实测** | 勘误 5：原稿称「F401 说明该符号无人使用，删掉即可」——**错误**。`tools.py` 非 `__init__.py`，裸转发导入会被 F401 全部报出（实测含确有调用点者），照删会删空整个壳。正解是显式声明 `__all__`，已补入 Step 6 代码块 |
| **旧路径搜索已修正** | 勘误 6：Task 3/4 原稿只用点号形式 `langchain\.tools` 验证「无残留」，**不足以**——斜杠形式 `langchain/tools` 不命中，实测漏掉 5 处（含 `docs/guides/ai-stack.md:76` 这条**可执行的开发指南**，它教人往已删除的文件里加工具）。已改为 `langchain[./]tools` 并列出全部漏网点 |
| **调用面已实测** | 11 处 import + 2 处 docstring 引用由 `rg` 全仓核实（见 Task 3 Step 1/2/4 的行号）。据此发现并修掉了两个计划缺陷：(1) `make_knowledge_search_tool` 有唯一消费者（测试），原计划未安排其迁移，已移入 Task 2 Step 7；(2) 无任何调用点从 `tools.py` 导入 13 个 DTO，故临时再导出层不做 `import *`，`inputs.py` 也不需要 `__all__` |

## 与设计文档的两处刻意偏差（已记录，非疏漏）

1. **设计 §5.2 写 `ToolDecl` 含 `slug` 字段**；实施改为**由声明表的键承载 slug**（`_DECLS: dict[str, ToolDecl]`），省去 13 次重复书写。行为无差异。
2. **设计 §7.1.2 写「3 个 spec 驱动工具」**；实际导出发现第 4 种情形 `mcp(input_schema=None)` 是**签名反推 schema** 的独立风险点，故 Task 1 的导出脚本含 `mcp_none` 一条（仅用于比对，不必填进 `_EXPECTED_SPEC_DRIVEN`），并在 Task 2 Step 5 以注释钉住「占位签名不得改动」。
