"""智能体定时任务 API Schema。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.common.cron import describe_cron


class AgentScheduleCreate(BaseModel):
    content: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="定时触发的提示内容或任务描述",
    )
    cron: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Cron 表达式（标准 5 段）",
    )
    enabled: bool = Field(default=True, description="创建后是否立即启用")


class AgentScheduleUpdate(BaseModel):
    content: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
        description="提示内容",
    )
    cron: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Cron 表达式",
    )
    enabled: bool | None = Field(default=None, description="是否启用")


class AgentScheduleOut(BaseModel):
    id: UUID = Field(description="定时任务 ID")
    agent_id: UUID = Field(description="所属智能体 ID")
    content: str = Field(description="触发内容")
    cron: str = Field(description="Cron 表达式")
    cron_description: str = Field(description="Cron 人类可读说明")
    enabled: bool = Field(description="是否启用")
    last_run_at: datetime | None = Field(default=None, description="上次执行时间")
    next_run_at: datetime | None = Field(default=None, description="下次计划执行时间")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")

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
