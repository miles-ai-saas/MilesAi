from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class HookExecutionLogOut(BaseModel):
    id: UUID
    hook_id: UUID
    binding_id: UUID | None
    event_id: UUID
    trace_id: str | None
    trigger: str
    scope: str
    target_id: UUID | None
    status: str
    http_status: int | None
    duration_ms: int | None
    response_action: str | None
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
