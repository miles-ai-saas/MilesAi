"""
平台内置工具注册为 LangChain ``StructuredTool``（纯 schema 构造库，无 DB、无执行）。

职责
----
- 内置工具 / 技能 ``skill_*`` / 生成 ``generate_*`` 的 schema 壳：``name``/
  ``description``/``args_schema`` 仅供 LLM 选型填参，不承载执行；
- 租户自定义 HTTP/SCRIPT 工具经 L1 loader 产出中性 ``CustomToolSpec``，再由
  ``build_platform_tools`` 聚合为 ``StructuredTool`` 列表；
- 本模块 ``func``/``_arun`` 均为占位——主循环从不直接执行 ``StructuredTool``，
  实际执行统一走 L1 ``invoke_tool_with_context``（含确认与审计），误调用即抛错提示。

与知识库相关
------------
``knowledge_search``：schema 壳仅供 LLM 工具描述，执行经 builtin 注册表
``handle_knowledge_search``（L1，走 ``vectorstores.search_kb``）。

生成类 / 技能类
---------------
``generate_*``、``skill_*`` 的 ``_arun`` 仅占位；schema 供 LLM 填参。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model

from app.models.tool.parameters import parameters_to_pydantic

# --- MCP 工具 → LLM function name（OpenAI 仅允许 [A-Za-z0-9_-]，≤64 字符）---

MCP_FUNCTION_PREFIX = "mcp__"
_MAX_FUNCTION_NAME = 64
_INVALID_IDENT_CHARS = re.compile(r"[^A-Za-z0-9_]")
_INVALID_FIELD_CHARS = re.compile(r"\W")


def sanitize_ident(raw: str) -> str:
    """把任意名称清洗为 `[A-Za-z0-9_]`；全非法时返回空串。"""
    return _INVALID_IDENT_CHARS.sub("_", str(raw or "")).strip("_")


def _service_ident(service_name: str) -> str:
    """服务标识：纯 ASCII 名称直接用；含中文等被清洗字符时追加 4 位哈希防塌缩碰撞。"""
    raw = str(service_name or "")
    cleaned = sanitize_ident(raw)
    if cleaned and cleaned == raw:
        return cleaned
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:4]
    return f"{cleaned or 'svc'}_{digest}"


def compose_mcp_tool_name(service_name: str, tool_name: str) -> str:
    """组合 MCP 工具的 function name：``mcp__{service}__{tool}``（超长则截断 + 短哈希）。

    服务名清洗有损（如含中文）时追加 4 位哈希；整体超长时追加 6 位摘要，
    保证同一 (service, tool) 稳定且几乎不碰撞。
    """
    svc = _service_ident(service_name)
    tool = sanitize_ident(tool_name) or "tool"
    name = f"{MCP_FUNCTION_PREFIX}{svc}__{tool}"
    if len(name) <= _MAX_FUNCTION_NAME:
        return name
    digest = hashlib.sha1(f"{service_name}\x00{tool_name}".encode("utf-8")).hexdigest()[:6]
    # prefix + svc + "__" + tool + "_" + digest ≤ 64
    budget = _MAX_FUNCTION_NAME - len(MCP_FUNCTION_PREFIX) - 2 - 1 - len(digest)
    svc_budget = min(len(svc), max(4, budget // 3))
    tool_budget = max(4, budget - svc_budget)
    return f"{MCP_FUNCTION_PREFIX}{svc[:svc_budget]}__{tool[:tool_budget]}_{digest}"


def is_mcp_tool_name(name: str | None) -> bool:
    """是否为绑定 MCP 服务的 function name。"""
    return bool(name) and str(name).startswith(MCP_FUNCTION_PREFIX)


def select_agent_tools(
    tools: list,
    allowed_slugs: list | None,
    *,
    always_allow: set[str] | None = None,
) -> list:
    """按 ``tool_slugs`` 白名单过滤工具列表。

    MCP 工具经 ``config.mcp_service_ids`` 绑定即视为启用，不受白名单过滤
    （未绑定时工具集合中本就不含 MCP，故不会意外放开）。
    ``always_allow`` 用于强制保留必需工具（如绑定 KB 时的 ``knowledge_search``）。
    """
    if not allowed_slugs:
        return list(tools)
    allowed = {str(s) for s in allowed_slugs} | set(always_allow or ())
    return [t for t in tools if t.name in allowed or is_mcp_tool_name(t.name)]


@dataclass(frozen=True)
class CustomToolSpec:
    """租户自定义工具的 L3 中性描述（L1 loader 自 ORM 构造）。"""

    slug: str
    name: str
    description: str | None
    tool_type: str  # "http" | "script"
    parameters: list[dict]


@dataclass(frozen=True)
class McpToolSpec:
    """绑定 MCP 服务中单个 tool 的 L3 中性描述（L1 loader 自 ``tools_cache`` 构造）。"""

    slug: str  # LLM function name，mcp__{service}__{tool}
    tool_name: str  # MCP tools/call 的原始 name
    service_id: str
    service_name: str
    description: str | None
    input_schema: dict | None  # MCP tools/list 的 inputSchema（JSON Schema）


def _field_name(raw: str) -> str:
    """把 JSON Schema 属性名转为合法 pydantic 字段名（保留可映射的清洗结果）。"""
    name = _INVALID_FIELD_CHARS.sub("_", str(raw or "")).strip("_")
    if not name or name[0].isdigit() or name.startswith("model_"):
        name = f"f_{name}" if name else "f_field"
    return name


def mcp_param_alias(input_schema: dict | None) -> dict[str, str]:
    """返回「pydantic 字段名 → JSON Schema 原始属性名」映射（仅含被清洗的键）。"""
    if not isinstance(input_schema, dict):
        return {}
    props = input_schema.get("properties")
    if not isinstance(props, dict):
        return {}
    return {_field_name(raw): raw for raw in props if _field_name(raw) != raw}


def json_schema_to_pydantic(input_schema: dict | None, *, model_name: str = "McpToolParams") -> type[BaseModel] | None:
    """把 MCP ``inputSchema``（JSON Schema）转为 pydantic 模型，供 LLM function schema 使用。

    支持 string/integer/number/boolean/object/array 与 enum；无可解析属性时返回 ``None``。
    仅用于生成 LLM 可见的 parameters schema，执行不经本模型。
    """
    if not isinstance(input_schema, dict):
        return None
    props = input_schema.get("properties")
    if not isinstance(props, dict) or not props:
        return None
    required = {str(r) for r in (input_schema.get("required") or [])}
    fields: dict[str, Any] = {}
    for raw_name, raw_prop in props.items():
        prop = raw_prop if isinstance(raw_prop, dict) else {}
        py_type = _json_scalar_type(prop.get("type"))
        is_required = raw_name in required
        if is_required:
            annotation: Any = py_type
            default: Any = ...
        else:
            annotation = py_type | None
            default = prop.get("default", None)
        extra: dict[str, Any] = {}
        enum = prop.get("enum")
        if isinstance(enum, list) and enum:
            extra["enum"] = enum
        fields[_field_name(raw_name)] = (
            annotation,
            Field(default=default, description=prop.get("description"), json_schema_extra=extra or None),
        )
    return create_model(model_name, **fields)


def _json_scalar_type(json_type: Any) -> Any:
    """JSON Schema type → python 类型；联合类型取首个非 null。"""
    if isinstance(json_type, list):
        json_type = next((t for t in json_type if t != "null"), None)
    return {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "object": dict,
        "array": list,
    }.get(json_type, Any)


# ``calculator`` 工具入参：单个数学表达式。
class CalculatorInput(BaseModel):
    expression: str = Field(..., description="数学表达式，如 1+2*3")


# ``http_request`` 工具入参：URL、请求方法与超时秒数。
class HttpRequestInput(BaseModel):
    url: str
    method: str = "GET"
    timeout: float = 10.0


# ``knowledge_search`` 工具入参：检索问题与知识库范围（单库 / 多库）。
class KnowledgeSearchInput(BaseModel):
    query: str = Field(..., description="检索问题")
    kb_id: str | None = Field(None, description="单个知识库 ID（与 kb_ids 二选一；可省略用智能体已绑定知识库）")
    kb_ids: list[str] | None = Field(None, description="多个知识库 ID；多库检索时优先使用")
    limit: int = Field(5, description="返回片段数")


# --- 生成类工具 schema（执行走 L1 invoke_tool_with_context，需 enable_generative_tools）---


# ``generate_image`` 工具入参：画面描述、尺寸、张数与可选参考图。
class GenerateImageInput(BaseModel):
    prompt: str = Field(
        ...,
        description="单幅完整画面描述。n>1 时仍写单图内容；除非用户明确要求组图/宫格/拼接，禁止四宫格或分镜拼贴",
    )
    size: str | None = Field(None, description="如 1024x1024；≥1280 边长或多张需用户确认")
    image_attachment_id: str | None = Field(None, description="参考图 attachment_id（如用户上传了图片并提供其 ID 时才填，通常不填）")
    n: int | None = Field(
        None,
        description="独立单图张数 1–4（不是一张图里的格子数）；≥3 需用户确认",
    )
    model_config_id: str | None = Field(None, description="生图模型 ID，留空自动使用默认模型，通常不需要填写")


# ``generate_video`` 工具入参：视频描述、时长、分辨率与可选首 / 尾帧图。
class GenerateVideoInput(BaseModel):
    prompt: str = Field(..., description="视频描述")
    duration: int | None = Field(None, description="时长秒数，默认 5")
    resolution: str | None = Field(None, description="720P 或 1080P")
    image_attachment_id: str | None = Field(None, description="首帧图 attachment_id（如用户上传了图片并提供其 ID 时才填，通常不填）")
    last_frame_attachment_id: str | None = Field(
        None,
        description="尾帧图 attachment_id（首尾帧生视频，须与首帧同传，通常不填）",
    )
    model_config_id: str | None = Field(None, description="生视频模型 ID，留空自动使用默认模型，通常不需要填写")


# ``get_current_datetime`` 工具入参：可选 IANA 时区。
class DateTimeInput(BaseModel):
    timezone: str | None = Field(None, description="IANA 时区，默认 UTC")


# ``skill_read_reference`` 工具入参：技能包内文件路径与最大读取字符数。
class SkillReadReferenceInput(BaseModel):
    path: str = Field(..., description="相对技能根的路径，如 references/guide.md")
    max_chars: int | None = Field(None, description="最大读取字符数，默认 12000")


# ``skill_run_script`` 工具入参：脚本路径、参数与超时 / 内存限制。
class SkillRunScriptInput(BaseModel):
    path: str = Field(..., description="scripts/ 下脚本路径，如 scripts/example.py")
    params: dict = Field(default_factory=dict, description="传入 run(params) 的参数字典")
    timeout_sec: int | None = Field(None, description="超时秒数，默认 30")
    max_memory_mb: int | None = Field(None, description="内存上限 MB，默认 512")


# --- L2 opt-in 内置工具 schema（须在 agent.config.tool_slugs 显式勾选才注入）---


# ``web_search`` 工具入参：关键词与返回条数。
class WebSearchInput(BaseModel):
    query: str = Field(..., description="搜索关键词")
    max_results: int | None = Field(None, description="返回条数，默认 5")


# ``code_execution`` 工具入参：代码片段、超时与内存上限。
class CodeExecutionInput(BaseModel):
    code: str = Field(..., description="Python 代码片段（须定义 run(params) 语义的片段；禁止 import）")
    timeout: int | None = Field(None, description="超时秒数，默认 30")
    memory: int | None = Field(None, description="内存上限 MB，默认 256")


# ``compliance_check_text`` 工具入参：待检测文本。
class ComplianceCheckTextInput(BaseModel):
    text: str = Field(..., description="待检测文本")


# ``run_flow_once`` 工具入参：流程 ID、入口变量与超时。
class RunFlowOnceInput(BaseModel):
    flow_id: str = Field(..., description="已发布流程的 UUID")
    inputs: dict | None = Field(None, description='流程入口变量字典，如 {"query": "..."}')
    query: str | None = Field(None, description="便捷传入流程 query 入口变量")
    timeout_sec: int | None = Field(None, description="执行超时秒数，默认 120，上限 300")


# ``invoke_tenant_hook`` 工具入参：触发时机、载荷与作用域。
class InvokeTenantHookInput(BaseModel):
    trigger: str = Field(
        ...,
        description="触发时机：before_call / after_call / before_reasoning / after_reasoning / before_tool / after_tool / on_error",
    )
    payload: dict | None = Field(None, description='传给钩子的载荷，如 {"query": "..."}')
    scope: str | None = Field(None, description="作用域：global（默认）/ agent / flow / tool / app")
    target_id: str | None = Field(None, description="作用域目标 ID（非 global 时使用）")


def _opt_in_marker(slug: str):
    """构造 opt-in 内置工具的占位 _arun（schema 供 LLM；执行走 L1 invoke_tool_with_context）。"""

    async def _arun(**kwargs: Any) -> dict:  # noqa: ARG001
        raise RuntimeError(f"请通过 invoke_tool_with_context 执行 {slug}")

    return _arun


def _make_web_search_tool() -> StructuredTool:
    return StructuredTool.from_function(
        coroutine=_opt_in_marker("web_search"),
        name="web_search",
        description="使用 DuckDuckGo 搜索网页，返回摘要与相关链接",
        args_schema=WebSearchInput,
    )


def _make_code_execution_tool() -> StructuredTool:
    return StructuredTool.from_function(
        coroutine=_opt_in_marker("code_execution"),
        name="code_execution",
        description="在 Runner 沙箱中执行 Python 代码片段（须符合安全校验）",
        args_schema=CodeExecutionInput,
    )


def _make_compliance_check_text_tool() -> StructuredTool:
    return StructuredTool.from_function(
        coroutine=_opt_in_marker("compliance_check_text"),
        name="compliance_check_text",
        description="检测文本是否命中租户敏感词库，返回命中词与 warn/block 处置建议（只读）",
        args_schema=ComplianceCheckTextInput,
    )


def _make_run_flow_once_tool() -> StructuredTool:
    return StructuredTool.from_function(
        coroutine=_opt_in_marker("run_flow_once"),
        name="run_flow_once",
        description="执行本租户一个已发布流程一次并返回其输出；仅限已发布流程，执行前需用户确认",
        args_schema=RunFlowOnceInput,
    )


def _make_invoke_tenant_hook_tool() -> StructuredTool:
    return StructuredTool.from_function(
        coroutine=_opt_in_marker("invoke_tenant_hook"),
        name="invoke_tenant_hook",
        description="手动触发本租户已绑定的 HTTP 钩子（按触发时机与作用域），返回各钩子状态与改写后的载荷",
        args_schema=InvokeTenantHookInput,
    )


_OPT_IN_BUILTIN_MAKERS: dict[str, Any] = {
    "web_search": _make_web_search_tool,
    "code_execution": _make_code_execution_tool,
    "compliance_check_text": _make_compliance_check_text_tool,
    "run_flow_once": _make_run_flow_once_tool,
    "invoke_tenant_hook": _make_invoke_tenant_hook_tool,
}


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
    return [maker() for slug, maker in _OPT_IN_BUILTIN_MAKERS.items() if slug in wanted]


def _make_calculator_tool() -> StructuredTool:
    """内置 calculator schema 壳；执行走 L1 invoke_tool_with_context。"""

    def _run(expression: str) -> dict:
        raise RuntimeError("请通过 invoke_tool_with_context 执行 calculator")

    return StructuredTool.from_function(
        func=_run,
        name="calculator",
        description="安全计算数学表达式",
        args_schema=CalculatorInput,
    )


def _make_http_request_tool() -> StructuredTool:
    """内置 http_request schema 壳；执行走 L1 invoke_tool_with_context。"""

    def _run(url: str, method: str = "GET", timeout: float = 10.0) -> dict:
        raise RuntimeError("请通过 invoke_tool_with_context 执行 http_request")

    return StructuredTool.from_function(
        func=_run,
        name="http_request",
        description="发起 HTTP 请求",
        args_schema=HttpRequestInput,
    )


def _make_datetime_tool() -> StructuredTool:
    """内置 get_current_datetime schema 壳；执行走 L1 invoke_tool_with_context。"""

    def _run(timezone: str | None = None) -> dict:
        raise RuntimeError("请通过 invoke_tool_with_context 执行 get_current_datetime")

    return StructuredTool.from_function(
        func=_run,
        name="get_current_datetime",
        description="获取当前的日期时间",
        args_schema=DateTimeInput,
    )


def make_knowledge_search_tool() -> StructuredTool:
    """
    内置「知识库检索」工具 schema 壳（单库、同步会话）。

    仅供 LLM 工具描述/选型；实际执行经 builtin 注册表 ``handle_knowledge_search``（L1），
    本壳 ``_run`` 明确报错，避免被当作可执行工具直接调用。
    """

    def _run(
        query: str,
        kb_id: str | None = None,
        kb_ids: list[str] | None = None,
        limit: int = 5,
    ) -> dict:
        raise RuntimeError("请通过 invoke_tool_with_context 执行 knowledge_search")

    return StructuredTool.from_function(
        func=_run,
        name="knowledge_search",
        description="在指定知识库中语义检索",
        args_schema=KnowledgeSearchInput,
    )


def _make_skill_read_reference_tool() -> StructuredTool:
    """技能包 references/ 读取；执行走 L1 invoke_tool_with_context，此处仅暴露 schema。"""

    async def _arun(path: str, max_chars: int | None = None) -> dict:
        raise RuntimeError("请通过 invoke_tool_with_context 执行 skill_read_reference")

    return StructuredTool.from_function(
        coroutine=_arun,
        name="skill_read_reference",
        description="读取绑定技能包 references/ 或 assets/ 下的文本文件",
        args_schema=SkillReadReferenceInput,
    )


def _make_skill_run_script_tool() -> StructuredTool:
    """技能包 scripts/ 沙箱执行；执行走 L1 invoke_tool_with_context，此处仅暴露 schema。"""

    async def _arun(
        path: str,
        params: dict | None = None,
        timeout_sec: int | None = None,
        max_memory_mb: int | None = None,
    ) -> dict:
        raise RuntimeError("请通过 invoke_tool_with_context 执行 skill_run_script")

    return StructuredTool.from_function(
        coroutine=_arun,
        name="skill_run_script",
        description="在沙箱中执行绑定技能包 scripts/ 下的 Python 脚本",
        args_schema=SkillRunScriptInput,
    )


def get_skill_bound_tools() -> list[StructuredTool]:
    """Agent 绑定 ``skill_package_id`` 时追加的技能工具对。"""
    return [_make_skill_read_reference_tool(), _make_skill_run_script_tool()]


def _make_generate_image_tool() -> StructuredTool:
    """generate_image schema；``enable_generative_tools`` 时挂载。"""

    async def _arun(
        prompt: str,
        size: str | None = None,
        image_attachment_id: str | None = None,
        n: int | None = None,
        model_config_id: str | None = None,
    ) -> dict:
        raise RuntimeError("请通过 invoke_tool_with_context 执行 generate_image")

    return StructuredTool.from_function(
        coroutine=_arun,
        name="generate_image",
        description="生成图片（文生图/图生图）。直接通过 function calling 调用，传入 prompt 等参数即可，禁止在文字中描述调用过程。",
        args_schema=GenerateImageInput,
    )


def _make_generate_video_tool() -> StructuredTool:
    """generate_video schema；异步 Celery 任务，对话中直接入队。"""

    async def _arun(
        prompt: str,
        duration: int | None = None,
        resolution: str | None = None,
        image_attachment_id: str | None = None,
        last_frame_attachment_id: str | None = None,
        model_config_id: str | None = None,
    ) -> dict:
        raise RuntimeError("请通过 invoke_tool_with_context 执行 generate_video")

    return StructuredTool.from_function(
        coroutine=_arun,
        name="generate_video",
        description="生成短视频（文/图生视频）。直接通过 function calling 调用，传入 prompt 等参数即可，禁止在文字中描述调用过程。耗时长，异步排队。",
        args_schema=GenerateVideoInput,
    )


def get_generative_tools() -> list[StructuredTool]:
    """由 ``build_platform_tools`` 在 ``agent.config.enable_generative_tools`` 时挂载。"""
    return [_make_generate_image_tool(), _make_generate_video_tool()]


def get_platform_tools() -> list[StructuredTool]:
    """返回内置工具列表（纯 schema 壳，无 DB/租户参数）。"""
    return [
        _make_calculator_tool(),
        _make_http_request_tool(),
        _make_datetime_tool(),
        make_knowledge_search_tool(),
    ]


def make_custom_http_tool(spec: CustomToolSpec) -> StructuredTool:
    """将租户 HTTP 工具（``CustomToolSpec``）转为 StructuredTool（schema 供 LLM；执行走 invoke）。"""
    schema = parameters_to_pydantic(spec.parameters)
    description = spec.description or spec.name
    slug = spec.slug

    async def _arun(**kwargs: Any) -> dict:
        raise RuntimeError(f"请通过 invoke_tool_with_context 执行 {slug}")

    return StructuredTool.from_function(
        coroutine=_arun,
        name=slug,
        description=description,
        args_schema=schema,
    )


def make_custom_script_tool(spec: CustomToolSpec) -> StructuredTool:
    """将租户 Python 脚本工具（``CustomToolSpec``）转为 StructuredTool（schema 供 LLM；执行走 invoke）。"""
    schema = parameters_to_pydantic(spec.parameters)
    description = spec.description or spec.name
    slug = spec.slug

    async def _arun(**kwargs: Any) -> dict:
        raise RuntimeError(f"请通过 invoke_tool_with_context 执行 {slug}")

    return StructuredTool.from_function(
        coroutine=_arun,
        name=slug,
        description=description,
        args_schema=schema,
    )


def make_mcp_tool(spec: McpToolSpec) -> StructuredTool:
    """将绑定 MCP 的单个 tool（``McpToolSpec``）转为 StructuredTool。

    schema 取自 ``inputSchema``（JSON Schema → pydantic），仅供 LLM 选型填参；
    实际执行走 L1 ``invoke_tool_with_context``（``source=mcp``）。
    """
    schema = json_schema_to_pydantic(spec.input_schema)
    description = spec.description or f"{spec.service_name} · {spec.tool_name}"
    slug = spec.slug

    async def _arun(**kwargs: Any) -> dict:
        raise RuntimeError(f"请通过 invoke_tool_with_context 执行 {slug}")

    kwargs: dict[str, Any] = {
        "coroutine": _arun,
        "name": slug,
        "description": description,
    }
    if schema is not None:
        kwargs["args_schema"] = schema
    return StructuredTool.from_function(**kwargs)


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
