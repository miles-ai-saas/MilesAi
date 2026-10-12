"""Agent SLA 聚合 API 响应模型。"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class AgentSlaMetrics(BaseModel):
    """一组调用的 SLA 指标。"""

    call_count: int = Field(description="调用次数")
    success_count: int = Field(default=0, description="成功次数")
    failed_count: int = Field(default=0, description="失败次数")
    blocked_count: int = Field(default=0, description="合规拦截次数")
    success_rate: float = Field(default=0.0, description="成功率（0–100）")
    latency_avg_ms: float = Field(default=0.0, description="平均延迟（毫秒）")
    latency_p50_ms: float = Field(default=0.0, description="P50 延迟（毫秒）")
    latency_p95_ms: float = Field(default=0.0, description="P95 延迟（毫秒）")
    tokens_per_call_avg: float = Field(default=0.0, description="平均 Token/次")
    total_tokens: int = Field(default=0, description="Token 合计")


class AgentSlaRouteRow(AgentSlaMetrics):
    route: str = Field(description="路由（如 rag / tool_agent / flow）")


class AgentSlaAgentRow(AgentSlaMetrics):
    agent_id: UUID = Field(description="智能体 ID")
    agent_name: str | None = Field(default=None, description="智能体名称")


class AgentSlaDailyPoint(BaseModel):
    date: str = Field(description="日期 YYYY-MM-DD")
    call_count: int = Field(default=0, description="当日调用次数")
    success_rate: float = Field(default=0.0, description="当日成功率（0–100）")
    latency_avg_ms: float = Field(default=0.0, description="当日平均延迟")


class AgentSlaReport(BaseModel):
    days: int = Field(description="统计窗口天数")
    agent_id: UUID | None = Field(default=None, description="可选智能体过滤")
    overview: AgentSlaMetrics = Field(description="窗口总览")
    by_route: list[AgentSlaRouteRow] = Field(default_factory=list, description="按路由聚合")
    by_agent: list[AgentSlaAgentRow] = Field(default_factory=list, description="按智能体 Top N")
    by_day: list[AgentSlaDailyPoint] = Field(default_factory=list, description="按日趋势")
