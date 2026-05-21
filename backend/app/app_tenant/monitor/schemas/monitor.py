from pydantic import BaseModel, Field

from app.app_tenant.tasks.schemas.task import TaskSummary


class MonitorStats(BaseModel):
    knowledge_bases: int
    documents: int
    agents: int
    flows: int
    intercept_logs_today: int
    pending_documents: int


class MonitorReport(BaseModel):
    stats: MonitorStats
    tasks: TaskSummary
    documents_by_status: dict[str, int] = Field(default_factory=dict)
    marketplace_installs: int = 0


class AlertConfig(BaseModel):
    enabled: bool = False
    webhook_url: str = ""
    notify_on_task_failed: bool = True
    notify_on_health_degraded: bool = True
