"""toolkit 契约冻结：16 个工具的对外可观测面在「拆分 + 声明式收敛」前后必须逐字节一致。

为什么必须存在：重构把 13 个工厂收敛为一张声明表，而 13 条 description 全部是中文、
最长 77 字符（177 UTF-8 字节），最长一条冻结的 schema 字面量达 889 字符，逐字搬运极易
出错；`StructuredTool` 又会**静默接受**把同步工具
写成异步（只是 `.func` 变空、`.coroutine` 非空，调用方看不出来）。本文件是这两类错误
唯一的拦截手段，故在重构**之前**先跑绿。

期望值来源：由重构前的实现实测导出（`args_schema.model_json_schema()` 经
`json.dumps(..., sort_keys=True, separators=(",", ":"))` 归一化），非人工手写。
"""

# 本文件的期望值块是实测导出的长数据（最长一条 schema 889 字符），刻意保持
# 「每个工具一行」以便与 Step 2 导出脚本的输出逐行 diff，故不拆行：整文件豁免
# E501；两个数据块另以 fmt: off / fmt: on 关闭 formatter 拆行（见其上方注释）。
# ruff: noqa: E501

from __future__ import annotations

import asyncio
import inspect
import json

import pytest

from miles_ai.integrations.langchain.toolkit import catalog
from miles_ai.integrations.langchain.toolkit.catalog import (
    build_platform_tools,
    get_generative_tools,
    get_platform_tools,
    get_skill_bound_tools,
    select_opt_in_builtin_tools,
)
from miles_ai.integrations.langchain.toolkit.specs import CustomToolSpec, McpToolSpec

_OPT_IN_SLUGS = ("web_search", "code_execution", "compliance_check_text", "run_flow_once", "invoke_tenant_hook")

# 每个工具一行：slug -> (description, is_async, args_schema 的归一化 JSON)
# 由重构前的实现实测导出（见 Step 2 的导出脚本），逐字复制，非人工手写。
# 逐行对应导出脚本输出，禁止 formatter 拆行（`# fmt: off` 须独立成行、后无文字）。
# fmt: off
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
    "mcp__svc__nofields": ("svc · nofields", True, '{"properties":{"kwargs":{"additionalProperties":true,"default":null,"title":"Kwargs","type":"object"}},"title":"mcp__svc__nofields","type":"object"}'),
}
# fmt: on


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
    platform_tools = get_platform_tools()
    assert platform_tools, "平台工具列表为空，本用例会空跑通过"
    for tool in platform_tools:
        assert tool.func is not None, f"{tool.name} 应使用同步 func"
        assert tool.coroutine is None, f"{tool.name} 不应被改成异步"


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


def test_decl_registry_and_groups_are_in_bijection() -> None:
    """``_DECLS`` 声明与四个分组必须双向一一对应（否则工具会**无征兆**地不可达）。

    为什么必须存在：``_DECLS`` 只在 ``_DECLS[slug]`` 处被查表，**从不被遍历**——一个工具的
    可见性完全取决于它是否落在 ``_PLATFORM_SLUGS`` / ``_OPT_IN_SLUGS`` / ``_SKILL_SLUGS`` /
    ``_GENERATIVE_SLUGS`` 之一。于是故障是**不对称**的：只加声明不加分组 → 构造列表时取不到，
    工具静默缺席且不报错；只加分组不加声明 → 构造时才 ``KeyError``。``docs/guides/ai-stack.md``
    正是教贡献者新增工具的可执行指南，故此处钉住双向一致。本用例不与其他用例重复：
    ``test_builtin_group_slugs_and_order`` 冻结的是四个分组的**当前内容**，
    ``test_builtin_tool_contract_frozen`` 的参数化来自本文件的 ``_EXPECTED_BUILTIN``——
    新增一条未归组的声明时，两者都会照旧通过。
    """
    assert catalog._DECLS, "声明表为空，本用例会空跑通过"
    groups = {
        "platform": catalog._PLATFORM_SLUGS,
        "opt_in": catalog._OPT_IN_SLUGS,
        "skill": catalog._SKILL_SLUGS,
        "generative": catalog._GENERATIVE_SLUGS,
    }
    seen: dict[str, str] = {}
    for group_name, slugs in groups.items():
        for slug in slugs:
            assert slug not in seen, f"{slug} 同时归入 {seen[slug]} 与 {group_name}，装配顺序将不确定"
            seen[slug] = group_name

    missing_group = sorted(set(catalog._DECLS) - set(seen))
    missing_decl = sorted(set(seen) - set(catalog._DECLS))
    assert not missing_group and not missing_decl, (
        f"已声明但未归组（任何工具列表都取不到、且不报错）: {missing_group}；已归组但无声明（构造时 KeyError）: {missing_decl}"
    )


def test_opt_in_gate_unchanged() -> None:
    """opt-in 工具未勾选不得注入；标量字符串与空配置的语义保持。"""
    assert select_opt_in_builtin_tools({}) == []
    assert select_opt_in_builtin_tools(None) == []
    assert select_opt_in_builtin_tools({"tool_slugs": []}) == []
    assert [t.name for t in select_opt_in_builtin_tools({"tool_slugs": "web_search"})] == ["web_search"]


def test_build_platform_tools_gate_matrix() -> None:
    """技能包 / 生成工具两个开关的四种组合（现状只覆盖技能那一半）。

    断言用**精确有序列表**而非集合：装配顺序（platform → opt-in → skill → generative
    → custom http/script → mcp）本身是本次重构「逐字节一致」的一部分，集合语义既看不出
    顺序，也发现不了重复工具。
    """
    skill = {"skill_package_id": "11111111-1111-1111-1111-111111111111"}
    gen = {"enable_generative_tools": True}
    platform_slugs = ["calculator", "http_request", "get_current_datetime", "knowledge_search"]

    def names(cfg: dict, custom=None, mcp=None) -> list[str]:
        return [t.name for t in build_platform_tools(cfg, custom, mcp)]

    assert names({}) == platform_slugs

    only_skill = names(skill)
    assert only_skill == [*platform_slugs, "skill_read_reference", "skill_run_script"]

    only_gen = names(gen)
    assert only_gen == [*platform_slugs, "generate_image", "generate_video"]

    # custom（http 先于 script）与 mcp 均参与时的完整拼接顺序。
    both_cfg = {**skill, **gen, "tool_slugs": list(_OPT_IN_SLUGS)}
    assert names(both_cfg, [_CUSTOM_HTTP], [_MCP]) == [
        *platform_slugs,
        *_OPT_IN_SLUGS,
        "skill_read_reference",
        "skill_run_script",
        "generate_image",
        "generate_video",
        "my_http",
        "mcp__github__create_issue",
    ]


@pytest.mark.parametrize("slug", sorted(_EXPECTED_SPEC_DRIVEN))
def test_spec_driven_tool_contract_frozen(slug: str) -> None:
    """spec 驱动的各类工具（custom http / custom script / mcp / mcp 无 schema）schema 与描述不变。"""
    expected_desc, expected_async, expected_schema = _EXPECTED_SPEC_DRIVEN[slug]
    tool = _spec_driven_tools()[slug]
    assert tool.description == expected_desc
    assert (tool.coroutine is not None) is expected_async
    assert _normalized(tool) == expected_schema


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
# 唯一 `input_schema is None` 的形态：`make_mcp_tool` 会整个省掉 args_schema，
# LangChain 遂从占位函数签名（`**kwargs`）反推 schema，title 取工具名。
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
    return {t.name: t for t in tools if t.name in {"my_http", "my_script", "mcp__github__create_issue", "mcp__svc__nofields"}}


_STUB_MESSAGE = "请通过 invoke_tool_with_context 执行 {slug}"


def _call_stub(tool) -> None:
    """调用占位函数本体（**不经** ``tool.invoke`` 的 pydantic 校验），让占位报错原样抛出。

    占位统一为 ``**kwargs``，无位置参数可传；这也正是 ``tool.invoke({})`` 测不到本意
    （会先抛 pydantic ``ValidationError``）的原因。
    """
    if tool.coroutine is not None:
        asyncio.run(tool.coroutine())
    else:
        tool.func()


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
    fn = tool.coroutine if tool.coroutine is not None else tool.func
    # 注意：本条断言与上方「期望值均由重构前实现实测导出」不同——它是**新增不变量**，
    # 不是冻结的旧行为。重构前平台/技能/生成工具的占位是带注解的具体签名（如
    # `def _run(expression: str)`），`**kwargs` 统一是本次 §5.2 的收敛决定。
    # 在此断言，是因为它同时挡两类回归：占位被改回带注解签名（会与 `input_schema=None`
    # 时靠签名反推 schema 的路径耦合），以及 `_call_stub` 的前提被破坏。
    positional = [p for p in inspect.signature(fn).parameters.values() if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    assert not positional, f"{slug} 的占位不应接受位置参数（统一为 **kwargs）"
    with pytest.raises(RuntimeError, match=_STUB_MESSAGE.format(slug=slug)):
        _call_stub(tool)


@pytest.mark.parametrize("slug", sorted(_EXPECTED_SPEC_DRIVEN))
def test_spec_driven_stub_raises_instead_of_executing(slug: str) -> None:
    tool = _spec_driven_tools()[slug]
    with pytest.raises(RuntimeError, match=_STUB_MESSAGE.format(slug=slug)):
        _call_stub(tool)
