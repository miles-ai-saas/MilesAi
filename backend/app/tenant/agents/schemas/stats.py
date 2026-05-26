"""智能体使用统计（按日序列；暂无服务端会话落库时返回零值）。"""

from pydantic import BaseModel, Field


class AgentStatsPoint(BaseModel):
    date: str = Field(description="ISO 日期 YYYY-MM-DD")
    value: float = 0


class AgentStatsOut(BaseModel):
    days: int
    sessions_total: int = 0
    active_users_total: int = 0
    messages_total: int = 0
    avg_rounds_total: float = 0
    sessions_by_day: list[AgentStatsPoint] = Field(default_factory=list)
    active_users_by_day: list[AgentStatsPoint] = Field(default_factory=list)
    messages_by_day: list[AgentStatsPoint] = Field(default_factory=list)
    avg_rounds_by_day: list[AgentStatsPoint] = Field(default_factory=list)
