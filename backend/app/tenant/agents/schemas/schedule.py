"""智能体定时任务 API Schema。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.common.cron import describe_cron


class AgentScheduleCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=500)
    cron: str = Field(..., min_length=1, max_length=64)
    enabled: bool = True


class AgentScheduleUpdate(BaseModel):
    content: str | None = Field(None, min_length=1, max_length=500)
    cron: str | None = Field(None, min_length=1, max_length=64)
    enabled: bool | None = None


class AgentScheduleOut(BaseModel):
    id: UUID
    agent_id: UUID
    content: str
    cron: str
    cron_description: str
    enabled: bool
    last_run_at: datetime | None
    next_run_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, entity) -> "AgentScheduleOut":
        return cls(
            id=entity.id,
            agent_id=entity.agent_id,
            content=entity.content,
            cron=entity.cron,
            cron_description=describe_cron(entity.cron),
            enabled=entity.enabled,
            last_run_at=entity.last_run_at,
            next_run_at=entity.next_run_at,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
