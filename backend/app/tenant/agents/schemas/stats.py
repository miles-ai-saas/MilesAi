"""智能体使用统计（按日序列，数据来自 agt_agent_chat_calls）。"""

from pydantic import BaseModel, Field


class AgentStatsPoint(BaseModel):
    date: str = Field(description="ISO 日期 YYYY-MM-DD")
    value: float = Field(default=0, description="当日指标值")


class AgentStatsOut(BaseModel):
    days: int = Field(description="统计窗口天数")
    sessions_total: int = Field(default=0, description="会话总数")
    active_users_total: int = Field(default=0, description="活跃用户数")
    messages_total: int = Field(default=0, description="消息总数")
    avg_rounds_total: float = Field(default=0, description="平均对话轮次")
    sessions_by_day: list[AgentStatsPoint] = Field(
        default_factory=list,
        description="按日会话数序列",
    )
    active_users_by_day: list[AgentStatsPoint] = Field(
        default_factory=list,
        description="按日活跃用户数序列",
    )
    messages_by_day: list[AgentStatsPoint] = Field(
        default_factory=list,
        description="按日消息数序列",
    )
    avg_rounds_by_day: list[AgentStatsPoint] = Field(
        default_factory=list,
        description="按日平均轮次序列",
    )
