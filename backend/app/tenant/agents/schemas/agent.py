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
    child_agent_id: UUID = Field(description="子智能体 ID")
    role_hint: str | None = Field(
        default=None,
        max_length=64,
        description="编排角色提示（如 retrieval、writer），供主智能体路由参考",
    )


class SubAgentRefOut(BaseModel):
    id: UUID = Field(description="子智能体 ID")
    name: str = Field(description="子智能体名称")
    role_hint: str | None = Field(default=None, description="绑定时的角色提示")
    status: AgentStatus = Field(description="子智能体启用状态")
    description: str | None = Field(default=None, description="子智能体描述")


class A2aPeerRefIn(BaseModel):
    peer_id: UUID = Field(description="A2A 对端 ID")
    role_hint: str | None = Field(
        default=None,
        max_length=64,
        description="对端在本智能体中的角色提示",
    )
    trigger_keywords: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="触发委托给该对端的关键词列表",
    )
    enabled: bool = Field(default=True, description="是否启用该对端绑定")


class A2aPeerRefOut(BaseModel):
    id: UUID = Field(description="A2A 对端 ID")
    name: str = Field(description="对端名称")
    role_hint: str | None = Field(default=None, description="绑定时的角色提示")
    trigger_keywords: list[str] = Field(
        default_factory=list,
        description="触发关键词列表",
    )
    enabled: bool = Field(description="绑定是否启用")
    status: str = Field(description="对端连接状态")
    card_display_name: str | None = Field(default=None, description="Agent Card 展示名")
    agent_card_url: str | None = Field(default=None, description="Agent Card URL")


class AgentCreate(BaseModel):
    """创建智能体；``kb_ids`` 可选，绑定后 chat 可走 RAG。"""

    agent_type: AgentType = Field(
        default=AgentType.CUSTOM,
        description="智能体类型：custom 自建 / a2a 外部对端",
    )
    category_id: UUID | None = Field(default=None, description="分类 ID")
    tag_ids: list[UUID] = Field(default_factory=list, description="标签 ID 列表")
    name: str = Field(..., min_length=1, max_length=128, description="智能体名称")
    description: str | None = Field(default=None, description="描述")
    system_prompt: str | None = Field(default=None, description="系统提示词")
    prompt_template_id: UUID | None = Field(default=None, description="关联提示词模板 ID")
    model_config_id: UUID | None = Field(default=None, description="默认大模型配置 ID")
    published_flow_id: UUID | None = Field(default=None, description="绑定的已发布流程 ID")
    kb_ids: list[UUID] = Field(default_factory=list, description="绑定的知识库 ID 列表")
    sub_agents: list[SubAgentBindingIn] = Field(
        default_factory=list,
        description="子智能体绑定",
    )
    a2a_peers: list[A2aPeerRefIn] = Field(
        default_factory=list,
        description="A2A 对端绑定",
    )
    config: dict = Field(default_factory=dict, description="扩展配置 JSON")


class AgentUpdate(BaseModel):
    agent_type: AgentType | None = Field(default=None, description="智能体类型")
    category_id: UUID | None = Field(default=None, description="分类 ID")
    tag_ids: list[UUID] | None = Field(default=None, description="标签 ID 列表（全量替换）")
    name: str | None = Field(default=None, description="智能体名称")
    description: str | None = Field(default=None, description="描述")
    status: AgentStatus | None = Field(default=None, description="启用状态")
    system_prompt: str | None = Field(default=None, description="系统提示词")
    prompt_template_id: UUID | None = Field(default=None, description="关联提示词模板 ID")
    model_config_id: UUID | None = Field(default=None, description="默认大模型配置 ID")
    published_flow_id: UUID | None = Field(default=None, description="绑定的已发布流程 ID")
    kb_ids: list[UUID] | None = Field(default=None, description="知识库 ID 列表（全量替换）")
    sub_agents: list[SubAgentBindingIn] | None = Field(
        default=None,
        description="子智能体绑定（全量替换）",
    )
    a2a_peers: list[A2aPeerRefIn] | None = Field(
        default=None,
        description="A2A 对端绑定（全量替换）",
    )
    config: dict | None = Field(default=None, description="扩展配置 JSON")


class AgentOut(BaseModel):
    id: UUID = Field(description="智能体 ID")
    tenant_id: UUID = Field(description="租户 ID")
    agent_type: AgentType = Field(description="智能体类型")
    category_id: UUID | None = Field(default=None, description="分类 ID")
    category_name: str | None = Field(default=None, description="分类名称")
    tags: list[TagRefOut] = Field(default_factory=list, description="标签列表")
    name: str = Field(description="名称")
    description: str | None = Field(default=None, description="描述")
    status: AgentStatus = Field(description="启用状态")
    system_prompt: str | None = Field(default=None, description="系统提示词")
    prompt_template_id: UUID | None = Field(default=None, description="提示词模板 ID")
    model_config_id: UUID | None = Field(default=None, description="默认模型配置 ID")
    published_flow_id: UUID | None = Field(default=None, description="已发布流程 ID")
    kb_ids: list[UUID] = Field(default_factory=list, description="绑定的知识库 ID 列表")
    sub_agents: list[SubAgentRefOut] = Field(default_factory=list, description="子智能体列表")
    a2a_peers: list[A2aPeerRefOut] = Field(default_factory=list, description="A2A 对端列表")
    config: dict = Field(description="扩展配置")
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}


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

    @model_validator(mode="after")
    def validate_query_or_media(self) -> "ChatRequest":
        if not self.query.strip() and not self.media:
            raise ValueError("query 与 media 不能同时为空")
        return self


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
    attachment_id: UUID = Field(description="附件 ID，用于鉴权内容 API")
    mime_type: str | None = Field(default=None, description="MIME 类型")
    caption: str | None = Field(default=None, description="展示说明")


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
