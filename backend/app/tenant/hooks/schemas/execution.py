from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class HookExecutionLogOut(BaseModel):
    id: UUID = Field(description="执行日志 ID")
    hook_id: UUID = Field(description="钩子定义 ID")
    binding_id: UUID | None = Field(default=None, description="绑定 ID")
    event_id: UUID = Field(description="触发事件 ID")
    trace_id: str | None = Field(default=None, description="链路追踪 ID")
    trigger: str = Field(description="触发时机")
    scope: str = Field(description="作用域")
    target_id: UUID | None = Field(default=None, description="作用域目标 ID")
    status: str = Field(description="执行状态")
    http_status: int | None = Field(default=None, description="HTTP 响应状态码")
    duration_ms: int | None = Field(default=None, description="执行耗时（毫秒）")
    response_action: str | None = Field(default=None, description="响应动作")
    error_message: str | None = Field(default=None, description="错误信息")
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}
