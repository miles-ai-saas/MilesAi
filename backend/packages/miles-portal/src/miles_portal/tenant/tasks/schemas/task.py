"""异步任务记录与批量取消相关的 schema。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from miles_portal.tenant.tasks.schemas.enums import TaskStatus


# 异步任务记录输出。
class TaskRecordOut(BaseModel):
    id: UUID = Field(description="任务记录 ID")
    tenant_id: UUID = Field(description="租户 ID")
    celery_task_id: str = Field(description="Celery 任务 ID")
    task_name: str = Field(description="任务名称")
    status: TaskStatus = Field(description="任务状态")
    resource_type: str | None = Field(default=None, description="关联资源类型")
    resource_id: UUID | None = Field(default=None, description="关联资源 ID")
    fail_reason: str | None = Field(default=None, description="失败原因")
    created_by: UUID | None = Field(default=None, description="创建人用户 ID")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")

    model_config = {"from_attributes": True}


# 按状态聚合的任务计数汇总。
class TaskSummary(BaseModel):
    pending: int = Field(default=0, description="待处理任务数")
    running: int = Field(default=0, description="运行中任务数")
    success: int = Field(default=0, description="成功任务数")
    failed: int = Field(default=0, description="失败任务数")
    cancelled: int = Field(default=0, description="已取消任务数")
    total: int = Field(default=0, description="任务总数")


# 批量取消任务的入参（单次上限 50）。
class TaskBatchCancelBody(BaseModel):
    task_ids: list[str] = Field(..., min_length=1, max_length=50, description="任务 ID 列表")


# 批量取消结果：已取消记录与跳过 ID。
class TaskBatchCancelResult(BaseModel):
    cancelled: list[TaskRecordOut] = Field(default_factory=list, description="已取消")
    skipped: list[str] = Field(default_factory=list, description="跳过（不存在或已结束）")
