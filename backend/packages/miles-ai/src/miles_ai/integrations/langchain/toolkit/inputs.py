"""内置工具 / 技能 / 生成类工具的入参 schema（纯声明，仅 LLM 可见）。

仅供 ``StructuredTool`` 的 ``args_schema`` 使用；执行不经这些模型。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


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
