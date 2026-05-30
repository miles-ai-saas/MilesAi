"""智能体对话会话 API 模型。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ChatSessionCreate(BaseModel):
    id: str | None = Field(default=None, max_length=128, description="可选，与前端 conversation_id 一致")
    title: str = Field(default="新对话", max_length=128)


class ChatSessionUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=128)


class ChatMessageOut(BaseModel):
    id: UUID
    role: str
    content: str
    media: list[dict] | None = None
    artifacts: list[dict] | None = None
    steps: list[dict] | None = None
    trace_id: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatSessionOut(BaseModel):
    id: str
    agent_id: UUID
    title: str
    message_count: int = 0
    created_at: datetime
    updated_at: datetime


class ChatSessionDetailOut(ChatSessionOut):
    messages: list[ChatMessageOut] = Field(default_factory=list)
