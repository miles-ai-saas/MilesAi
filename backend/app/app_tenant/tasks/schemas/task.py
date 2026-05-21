from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.task import TaskStatus


class TaskRecordOut(BaseModel):
    id: UUID
    tenant_id: UUID
    celery_task_id: str
    task_name: str
    status: TaskStatus
    resource_type: str | None
    resource_id: UUID | None
    fail_reason: str | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskSummary(BaseModel):
    pending: int = 0
    running: int = 0
    success: int = 0
    failed: int = 0
    cancelled: int = 0
    total: int = 0
