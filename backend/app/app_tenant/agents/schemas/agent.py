from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.agent import AgentStatus


class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    system_prompt: str | None = None
    prompt_template_id: UUID | None = None
    model_config_id: UUID | None = None
    published_flow_id: UUID | None = None
    kb_ids: list[UUID] = []
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
    config: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1)
    inputs: dict = {}


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict] = []
    steps: list[dict] = []
