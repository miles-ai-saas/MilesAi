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

from dataclasses import dataclass
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model

from app.common.exceptions import BadRequestError


@dataclass(frozen=True)
class CustomToolSpec:
    """租户自定义工具的 L3 中性描述（L1 loader 自 ORM 构造）。"""

    slug: str
    name: str
    description: str | None
    tool_type: str  # "http" | "script"
    parameters: list[dict]


# --- 参数列表 → Pydantic schema（纯函数，本地复刻 tenant.tools.parameters
# --- 以保证本模块对 tenant 引用清零；schema 语义与原实现完全一致）---


_ALLOWED_TYPES = {"string", "number", "integer", "boolean"}


def _normalize_parameters(raw: list | None) -> list[dict]:
    if not raw:
        return []
    names: set[str] = set()
    out: list[dict] = []
    for i, p in enumerate(raw):
        if not isinstance(p, dict):
            raise BadRequestError(f"parameters[{i}] 必须是对象")
        name = str(p.get("name", "")).strip()
        if not name or not name.replace("_", "").isalnum() or not name[0].isalpha():
            raise BadRequestError(f"parameters[{i}].name 无效: {name!r}")
        if name in names:
            raise BadRequestError(f"参数名重复: {name}")
        names.add(name)
        ptype = str(p.get("type", "string"))
        if ptype not in _ALLOWED_TYPES:
            raise BadRequestError(f"parameters[{i}].type 不支持: {ptype}")
        out.append({**p, "name": name, "type": ptype})
    return out


def parameters_to_pydantic(schema: list[dict]) -> type[BaseModel]:
    """将自定义工具参数列表动态构建为 Pydantic 模型（本地纯函数，schema 语义一致）。"""
    schema = _normalize_parameters(schema)
    fields: dict[str, Any] = {}
    for p in schema:
        py_type = {"string": str, "integer": int, "number": float, "boolean": bool}[p["type"]]
        default = ... if p.get("required") else p.get("default", None)
        fields[p["name"]] = (py_type, Field(default=default, description=p.get("description")))
    return create_model("ToolParams", **fields)


class CalculatorInput(BaseModel):
    expression: str = Field(..., description="数学表达式，如 1+2*3")


class HttpRequestInput(BaseModel):
    url: str
    method: str = "GET"
    timeout: float = 10.0


class KnowledgeSearchInput(BaseModel):
    query: str
    kb_id: str
    limit: int = 5


# --- 生成类工具 schema（执行走 L1 invoke_tool_with_context，需 enable_generative_tools）---


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


class DateTimeInput(BaseModel):
    timezone: str | None = Field(None, description="IANA 时区，默认 UTC")


class SkillReadReferenceInput(BaseModel):
    path: str = Field(..., description="相对技能根的路径，如 references/guide.md")
    max_chars: int | None = Field(None, description="最大读取字符数，默认 12000")


class SkillRunScriptInput(BaseModel):
    path: str = Field(..., description="scripts/ 下脚本路径，如 scripts/example.py")
    params: dict = Field(default_factory=dict, description="传入 run(params) 的参数字典")
    timeout_sec: int | None = Field(None, description="超时秒数，默认 30")
    max_memory_mb: int | None = Field(None, description="内存上限 MB，默认 512")


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

    def _run(query: str, kb_id: str, limit: int = 5) -> dict:
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
