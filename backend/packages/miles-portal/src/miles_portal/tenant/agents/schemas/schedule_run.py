"""定时任务执行历史 schema。"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from miles_core.models.agent.schedule_run import AgentScheduleRun


# 定时任务单次执行记录输出。
class AgentScheduleRunOut(BaseModel):
    id: UUID = Field(description="执行记录 ID")
    schedule_id: UUID = Field(description="定时任务 ID")
    agent_id: UUID = Field(description="智能体 ID")
    status: str = Field(description="success | failed")
    started_at: datetime = Field(description="开始时间")
    finished_at: datetime | None = Field(default=None, description="结束时间")
    error_message: str | None = Field(default=None, description="失败原因")

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, entity: AgentScheduleRun) -> AgentScheduleRunOut:
        """由 ``AgentScheduleRun`` ORM 实体校验转换为输出模型。"""
        return cls.model_validate(entity)
