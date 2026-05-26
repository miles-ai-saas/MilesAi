"""
智能体 HTTP 请求/响应模型。

``kb_ids`` 写入 ``agt_kb_bindings``；对话时转为字符串列表传入 RAG/流程 ``RunContext``。
``ChatRequest.conversation_id`` 参与 LangGraph ``thread_id``（多轮 checkpoint）。
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.common.schemas.media import MediaRefIn
from app.models.agent import AgentStatus, AgentType
from app.tenant.tags.schemas.tag import TagRefOut


class SubAgentBindingIn(BaseModel):
    child_agent_id: UUID
    role_hint: str | None = Field(None, max_length=64)


class SubAgentRefOut(BaseModel):
    id: UUID
    name: str
    role_hint: str | None = None
    status: AgentStatus
    description: str | None = None


class A2aPeerRefIn(BaseModel):
    peer_id: UUID
    role_hint: str | None = Field(None, max_length=64)
    trigger_keywords: list[str] = Field(default_factory=list, max_length=20)
    enabled: bool = True


class A2aPeerRefOut(BaseModel):
    id: UUID
    name: str
    role_hint: str | None = None
    trigger_keywords: list[str] = []
    enabled: bool = True
    status: str
    card_display_name: str | None = None
    agent_card_url: str | None = None


class AgentCreate(BaseModel):
    """创建智能体；``kb_ids`` 可选，绑定后 chat 可走 RAG。"""

    agent_type: AgentType = AgentType.CUSTOM
    category_id: UUID | None = None
    tag_ids: list[UUID] = []
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    system_prompt: str | None = None
    prompt_template_id: UUID | None = None
    model_config_id: UUID | None = None
    published_flow_id: UUID | None = None
    kb_ids: list[UUID] = []
    sub_agents: list[SubAgentBindingIn] = []
    a2a_peers: list[A2aPeerRefIn] = []
    config: dict = {}


class AgentUpdate(BaseModel):
    agent_type: AgentType | None = None
    category_id: UUID | None = None
    tag_ids: list[UUID] | None = None
    name: str | None = None
    description: str | None = None
    status: AgentStatus | None = None
    system_prompt: str | None = None
    prompt_template_id: UUID | None = None
    model_config_id: UUID | None = None
    published_flow_id: UUID | None = None
    kb_ids: list[UUID] | None = None
    sub_agents: list[SubAgentBindingIn] | None = None
    a2a_peers: list[A2aPeerRefIn] | None = None
    config: dict | None = None


class AgentOut(BaseModel):
    id: UUID
    tenant_id: UUID
    agent_type: AgentType
    category_id: UUID | None = None
    category_name: str | None = None
    tags: list[TagRefOut] = []
    name: str
    description: str | None
    status: AgentStatus
    system_prompt: str | None
    prompt_template_id: UUID | None
    model_config_id: UUID | None
    published_flow_id: UUID | None
    kb_ids: list[UUID] = []
    sub_agents: list[SubAgentRefOut] = []
    a2a_peers: list[A2aPeerRefOut] = []
    config: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatMediaIn(MediaRefIn):
    """智能体对话附图（与 ``MediaRefIn`` 同形）。"""


class ChatRequest(BaseModel):
    """对话入参；``inputs`` 合并进流程画布运行时变量。"""

    query: str = Field(default="", max_length=32000)
    media: list[ChatMediaIn] = Field(
        default_factory=list,
        description="识图附图；服务端转 data URL，非签名 OSS URL",
    )
    inputs: dict = {}
    conversation_id: str | None = Field(
        None,
        max_length=128,
        description="同一会话 thread_id 后缀，用于 LangGraph checkpoint 多轮恢复",
    )
    tool_confirmed: bool = False
    pending_tool_slug: str | None = None
    pending_tool_params: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_query_or_media(self) -> "ChatRequest":
        if not self.query.strip() and not self.media:
            raise ValueError("query 与 media 不能同时为空")
        return self


class PendingToolCall(BaseModel):
    slug: str
    name: str
    description: str | None = None
    params: dict = Field(default_factory=dict)


class ChatArtifact(BaseModel):
    """工具生图/生视频等产出物；前端经鉴权 content API 预览，非 OSS 签名 URL。"""

    kind: str = "image"  # image | video | audio（扩展）
    attachment_id: UUID
    mime_type: str | None = None
    caption: str | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict] = []
    steps: list[dict] = []
    artifacts: list[ChatArtifact] = Field(
        default_factory=list,
        description="generate_image / generate_video 等工具的结构化产出",
    )
    pending_tool: PendingToolCall | None = None
