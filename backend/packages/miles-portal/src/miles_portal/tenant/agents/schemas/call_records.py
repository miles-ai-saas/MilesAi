"""智能体对话调用记录 API 模型。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from miles_portal.tenant.hooks.schemas.execution import HookExecutionLogOut
from miles_portal.tenant.tools.schemas.tools import ToolInvocationLogOut


# 单条对话调用记录的列表输出。
class AgentCallRecordOut(BaseModel):
    id: UUID
    agent_id: UUID
    conversation_id: str | None = None
    trace_id: str | None = None
    actor_user_id: UUID | None = None
    actor_username: str | None = None
    status: str
    route: str
    query_preview: str
    answer_preview: str
    latency_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    step_count: int = 0
    tool_call_count: int = 0
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# 调用记录详情，附带步骤摘要与关联的工具/钩子日志。
class AgentCallRecordDetailOut(AgentCallRecordOut):
    meta: dict = Field(default_factory=dict)
    steps_summary: list[dict] | None = None
    related_tool_logs: list[ToolInvocationLogOut] = Field(default_factory=list)
    related_hook_logs: list[HookExecutionLogOut] = Field(default_factory=list)
