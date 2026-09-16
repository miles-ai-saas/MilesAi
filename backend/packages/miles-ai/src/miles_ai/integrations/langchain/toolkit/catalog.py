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
from typing import TYPE_CHECKING, Any

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
from .specs import json_schema_to_pydantic

if TYPE_CHECKING:
    # 仅用于本模块的函数签名注解（``from __future__ import annotations`` 下不求值）。
    # 刻意**不**在 ``__all__`` 里再导出：设计要求按职责 import——需要这两个 DTO 的调用点
    # 应直接 ``from ...toolkit.specs import ...``，否则 catalog 会变成第二条入口，与
    # ``toolkit/__init__.py`` 必须为空是同一条约束。
    from .specs import CustomToolSpec, McpToolSpec

__all__ = [
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
