"""智能体对话 IO 契约（中立域，L3/tenant 共用）。

``ChatRequest``/``ChatResponse`` 与 ``ChatArtifact``/``PendingToolCall``/``ChatMediaIn``
为对话入口/响应与工具产出物的纯 pydantic 契约，供 L1（``tenant.agents.schemas.agent``
re-export）与 L3 ``integrations/langchain/tool_agent`` 共用。定义自
``tenant/agents/schemas/agent.py`` 下沉（路径稳定，L1 引用不变）；
新代码 L3 应指向本模块，禁止反向依赖 ``tenant``。
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.common.schemas.media import MediaRefIn


class ChatMediaIn(MediaRefIn):
    """智能体对话附图（与 ``MediaRefIn`` 同形）。"""


class ChatRequest(BaseModel):
    """对话入参；``inputs`` 合并进流程画布运行时变量。"""

    query: str = Field(
        default="",
        max_length=32000,
        description="用户问题文本",
    )
    media: list[ChatMediaIn] = Field(
        default_factory=list,
        description="识图附图；服务端转 data URL，非签名 OSS URL",
    )
    inputs: dict = Field(
        default_factory=dict,
        description="附加运行时变量，合并进流程画布 RunContext.inputs",
    )
    conversation_id: str | None = Field(
        default=None,
        max_length=128,
        description="同一会话 thread_id 后缀，用于 LangGraph checkpoint 多轮恢复",
    )
    tool_confirmed: bool = Field(
        default=False,
        description="是否确认执行待审批的工具调用",
    )
    pending_tool_slug: str | None = Field(
        default=None,
        description="待确认的工具 slug（与 pending_tool_params 配套）",
    )
    pending_tool_params: dict = Field(
        default_factory=dict,
        description="待确认工具的参数",
    )
    generative_image_n: int = Field(
        default=1,
        ge=1,
        le=4,
        description="输入区生图数量；平台强制覆盖 tool 入参 n，1–4",
    )
    generative_video_duration: int = Field(
        default=5,
        ge=1,
        le=15,
        description="输入区视频时长预设（秒），LLM 不指定 duration 时用此值；1–15",
    )

    @model_validator(mode="after")
    def validate_query_or_media(self) -> "ChatRequest":
        """query 与 media 至少一项非空，否则校验失败。"""
        if not self.query.strip() and not self.media:
            raise ValueError("query 与 media 不能同时为空")
        return self


# 待用户确认后执行的工具调用（slug 与参数）。
class PendingToolCall(BaseModel):
    slug: str = Field(description="工具 slug")
    name: str = Field(description="工具展示名")
    description: str | None = Field(default=None, description="工具说明")
    params: dict = Field(default_factory=dict, description="待执行参数")


class ChatArtifact(BaseModel):
    """工具生图/生视频等产出物；前端经鉴权 content API 预览，非 OSS 签名 URL。"""

    kind: str = Field(
        default="image",
        description="产物类型：image | video | audio（扩展）",
    )
    attachment_id: UUID | None = Field(default=None, description="附件 ID；pending 时可空")
    mime_type: str | None = Field(default=None, description="MIME 类型")
    caption: str | None = Field(default=None, description="展示说明")
    status: str | None = Field(
        default=None,
        description="pending | running | success | failed | cancelled；缺省且有 attachment 视为 success",
    )
    job_id: str | None = Field(default=None, description="异步 generative job id")
    media_asset_id: UUID | None = Field(default=None, description="生成素材 ID")
    progress_percent: int | None = Field(default=None, description="0-100")
    progress_message: str | None = Field(default=None, description="进度文案")
    error_message: str | None = Field(default=None, description="失败文案")


# 对话响应：正文、RAG 来源、步骤轨迹与工具产出物。
class ChatResponse(BaseModel):
    answer: str = Field(description="助手回复正文")
    sources: list[dict] = Field(
        default_factory=list,
        description="RAG 引用来源（chunk 元数据列表）",
    )
    steps: list[dict] = Field(
        default_factory=list,
        description="执行步骤轨迹（调试用）",
    )
    artifacts: list[ChatArtifact] = Field(
        default_factory=list,
        description="generate_image / generate_video 等工具的结构化产出",
    )
    pending_tool: PendingToolCall | None = Field(
        default=None,
        description="需用户确认后执行的工具调用",
    )
    generative_jobs: list[dict] = Field(
        default_factory=list,
        description="异步生成任务（如 pending 的生视频 job_id），供前端轮询",
    )
