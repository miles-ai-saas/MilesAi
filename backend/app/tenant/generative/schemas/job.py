"""生成任务 HTTP 请求/响应模型。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.model.generative_job import GenerativeJobStatus


# 生成任务详情输出。
class GenerativeJobOut(BaseModel):
    id: UUID = Field(description="任务 ID")
    tenant_id: UUID = Field(description="租户 ID")
    kind: str = Field(description="任务类型：video 等")
    status: GenerativeJobStatus = Field(description="任务状态")
    source: str = Field(description="来源：agent_tool | flow_node | api")
    progress_message: str | None = Field(default=None, description="进度说明")
    progress_percent: int | None = Field(default=None, description="进度 0–100")
    params: dict = Field(default_factory=dict, description="提交参数快照")
    result: dict | None = Field(default=None, description="成功时的产物（含 attachment_id）")
    error_message: str | None = Field(default=None, description="失败原因")
    celery_task_id: str | None = Field(default=None, description="Celery 任务 ID")
    celery_task_record_id: UUID | None = Field(
        default=None,
        description="关联 Celery 任务记录 ID（后台任务 Tab）",
    )
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")

    model_config = {"from_attributes": True}


# 提交生视频任务的入参。
class VideoGenerativeJobCreate(BaseModel):
    prompt: str = Field(..., min_length=1, description="视频描述")
    duration: int | None = Field(default=5, description="时长（秒）")
    resolution: str | None = Field(default=None, description="720P / 1080P")
    image_attachment_id: UUID | None = Field(default=None, description="首帧图")
    last_frame_attachment_id: UUID | None = Field(default=None, description="尾帧图")
    model_config_id: UUID | None = Field(default=None, description="video_gen 模型配置")


# 提交生图任务的入参。
class ImageGenerativeJobCreate(BaseModel):
    prompt: str = Field(..., min_length=1, description="生图描述")
    size: str | None = Field(default=None, description="如 1024x1024")
    n: int | None = Field(default=1, ge=1, le=4, description="生成张数")
    image_attachment_id: UUID | None = Field(default=None, description="图生图参考图")
    model_config_id: UUID | None = Field(default=None, description="image_gen 模型配置")


# 批量取消生成任务的入参。
class GenerativeJobBatchCancelBody(BaseModel):
    job_ids: list[UUID] = Field(..., min_length=1, max_length=50, description="生成任务 ID 列表")


# 批量取消结果：已取消任务列表与跳过 ID。
class GenerativeJobBatchCancelResult(BaseModel):
    cancelled: list[GenerativeJobOut] = Field(default_factory=list, description="已取消")
    skipped: list[str] = Field(default_factory=list, description="跳过（不存在或已结束）")
