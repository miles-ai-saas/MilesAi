"""运行监控 API 响应模型（统计、趋势、告警、模型用量）。"""

from pydantic import BaseModel, Field
from uuid import UUID

from app.tenant.tasks.schemas.task import TaskSummary


# 资源与合规概览计数。
class MonitorStats(BaseModel):
    knowledge_bases: int = Field(description="知识库数量")
    documents: int = Field(description="文档数量")
    image_documents: int = Field(default=0, description="图片文档数量（OCR）")
    audio_documents: int = Field(default=0, description="音频文档数量（Whisper）")
    video_documents: int = Field(default=0, description="视频文档数量")
    agents: int = Field(description="智能体数量")
    flows: int = Field(description="流程数量")
    intercept_logs_today: int = Field(description="今日合规拦截次数")
    pending_documents: int = Field(description="待处理文档数量")


# 监控总览响应（资源统计 + 任务汇总 + 文档状态）。
class MonitorReport(BaseModel):
    stats: MonitorStats = Field(description="资源统计概览")
    tasks: TaskSummary = Field(description="异步任务汇总")
    documents_by_status: dict[str, int] = Field(
        default_factory=dict,
        description="按状态分组的文档数量",
    )
    marketplace_installs: int = Field(default=0, description="应用广场安装次数")


# 告警开关与通知渠道配置。
class AlertConfig(BaseModel):
    enabled: bool = Field(default=False, description="是否启用告警")
    webhook_url: str = Field(default="", description="Webhook 通知地址")
    email_notify_to: str = Field(default="", description="告警邮件接收人（逗号分隔）")
    notify_on_task_failed: bool = Field(default=True, description="任务失败时通知")
    notify_on_health_degraded: bool = Field(default=True, description="健康检查降级时通知")


# 单日任务状态分布。
class TaskTrendPoint(BaseModel):
    date: str = Field(description="日期（YYYY-MM-DD）")
    pending: int = Field(default=0, description="待处理任务数")
    running: int = Field(default=0, description="运行中任务数")
    success: int = Field(default=0, description="成功任务数")
    failed: int = Field(default=0, description="失败任务数")
    cancelled: int = Field(default=0, description="已取消任务数")
    total: int = Field(default=0, description="任务总数")


# 任务与合规拦截的按日趋势。
class MonitorTrends(BaseModel):
    task_by_day: list[TaskTrendPoint] = Field(
        default_factory=list,
        description="按日任务趋势",
    )
    intercept_by_day: list[dict[str, int | str]] = Field(
        default_factory=list,
        description="按日合规拦截趋势",
    )


# 单模型 Token 用量聚合行。
class ModelUsageRow(BaseModel):
    model_config_id: UUID | None = Field(default=None, description="模型配置 ID")
    model_name: str = Field(description="模型名称")
    call_count: int = Field(description="调用次数")
    prompt_tokens: int = Field(description="输入 Token")
    completion_tokens: int = Field(description="输出 Token")
    total_tokens: int = Field(description="总 Token")


# 按天统计的模型 Token 用量报表。
class ModelUsageReport(BaseModel):
    days: int = Field(description="统计天数")
    rows: list[ModelUsageRow] = Field(default_factory=list, description="按模型聚合")
    total_tokens: int = Field(default=0, description="总 Token")
