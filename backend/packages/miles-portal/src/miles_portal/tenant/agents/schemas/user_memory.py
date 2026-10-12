"""跨会话用户记忆 API 模型。"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class UserMemoryItemOut(BaseModel):
    id: UUID
    kind: str = Field(description="summary | preference")
    content: str
    source_trace_id: str | None = None
    updated_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class UserMemoryListOut(BaseModel):
    items: list[UserMemoryItemOut] = Field(default_factory=list)
