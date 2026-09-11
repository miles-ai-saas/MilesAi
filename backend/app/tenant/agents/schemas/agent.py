"""
智能体 HTTP 请求/响应模型。

``kb_ids`` 写入 ``agt_kb_bindings``；对话时转为字符串列表传入 RAG/流程 ``RunContext``。
``ChatRequest.conversation_id`` 参与 LangGraph ``thread_id``（多轮 checkpoint）。
对话 IO 契约（Chat* 五类）定义已下沉 ``app.models.agent.chat_io``，本处 re-export 保持 L1 import 路径。
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.agent import AgentStatus, AgentType
from app.models.agent.chat_io import (  # noqa: F401 — re-export（Chat* 五类）
    ChatArtifact,
    ChatMediaIn,
    ChatRequest,
    ChatResponse,
    PendingToolCall,
)
from app.tenant.tags.schemas.tag import TagRefOut


# 子智能体绑定入参。
class SubAgentBindingIn(BaseModel):
    child_agent_id: UUID = Field(description="子智能体 ID")
    role_hint: str | None = Field(
        default=None,
        max_length=64,
        description="编排角色提示（如 retrieval、writer），供主智能体路由参考",
    )


# 子智能体绑定的对外展示。
class SubAgentRefOut(BaseModel):
    id: UUID = Field(description="子智能体 ID")
    name: str = Field(description="子智能体名称")
    role_hint: str | None = Field(default=None, description="绑定时的角色提示")
    status: AgentStatus = Field(description="子智能体启用状态")
    description: str | None = Field(default=None, description="子智能体描述")


# A2A 对端绑定入参。
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


# A2A 对端绑定的对外展示，含连接状态与 Agent Card。
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


# 更新智能体；未提供字段保持不变，列表类字段为全量替换。
class AgentUpdate(BaseModel):
    agent_type: AgentType | None = Field(default=None, description="智能体类型")
    category_id: UUID | None = Field(default=None, description="分类 ID")
    tag_ids: list[UUID] | None = Field(default=None, description="标签 ID 列表（全量替换）")
    name: str | None = Field(default=None, min_length=1, max_length=128, description="智能体名称")
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


# 智能体详情/列表的对外展示。
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


class AgentPackage(BaseModel):
    """智能体导入/导出包。"""

    version: str = Field(default="1.0", description="包格式版本")
    agent: AgentCreate = Field(description="智能体创建参数")
