from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.agent import AgentStatus


class SubAgentBindingIn(BaseModel):
    child_agent_id: UUID
    role_hint: str | None = Field(None, max_length=64)


class SubAgentRefOut(BaseModel):
    id: UUID
    name: str
    role_hint: str | None = None
    status: AgentStatus
    description: str | None = None


class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    system_prompt: str | None = None
    prompt_template_id: UUID | None = None
    model_config_id: UUID | None = None
    published_flow_id: UUID | None = None
    kb_ids: list[UUID] = []
    sub_agents: list[SubAgentBindingIn] = []
    config: dict = {}


class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: AgentStatus | None = None
    system_prompt: str | None = None
    prompt_template_id: UUID | None = None
    model_config_id: UUID | None = None
    published_flow_id: UUID | None = None
    kb_ids: list[UUID] | None = None
    sub_agents: list[SubAgentBindingIn] | None = None
    config: dict | None = None


class AgentOut(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    status: AgentStatus
    system_prompt: str | None
    prompt_template_id: UUID | None
    model_config_id: UUID | None
    published_flow_id: UUID | None
    kb_ids: list[UUID] = []
    sub_agents: list[SubAgentRefOut] = []
    config: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1)
    inputs: dict = {}
    conversation_id: str | None = Field(
        None,
        max_length=128,
        description="同一会话 thread_id 后缀，用于 LangGraph checkpoint 多轮恢复",
    )


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict] = []
    steps: list[dict] = []
