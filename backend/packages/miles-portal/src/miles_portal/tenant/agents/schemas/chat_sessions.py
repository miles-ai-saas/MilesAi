"""智能体对话会话 API 模型。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# 创建会话入参；``id`` 可指定为与前端 ``conversation_id`` 一致。
class ChatSessionCreate(BaseModel):
    id: str | None = Field(default=None, max_length=128, description="可选，与前端 conversation_id 一致")
    title: str = Field(default="新对话", max_length=128)


# 更新会话入参（当前仅支持标题）。
class ChatSessionUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=128)


# 单条会话消息输出，含媒体、产物与执行步骤。
class ChatMessageOut(BaseModel):
    id: UUID
    role: str
    content: str
    sort_index: int
    media: list[dict] | None = None
    artifacts: list[dict] | None = None
    steps: list[dict] | None = None
    trace_id: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# 会话摘要输出。
class ChatSessionOut(BaseModel):
    id: str
    agent_id: UUID
    title: str
    message_count: int = 0
    created_at: datetime
    updated_at: datetime


# 会话详情，含当页消息与是否还有更早消息。
class ChatSessionDetailOut(ChatSessionOut):
    messages: list[ChatMessageOut] = Field(default_factory=list)
    has_more: bool = Field(default=False, description="是否还有更早的消息（游标分页）")
