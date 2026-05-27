"""审计/日志 ORM 与迁移列一致（无 deleted_at）。"""

from app.models.agent_schedule_run import AgentScheduleRun
from app.models.model_usage_log import ModelUsageLog
from app.tenant.hooks.models import HookExecutionLog


def test_audit_log_models_have_no_deleted_at_column():
    for model in (ModelUsageLog, HookExecutionLog, AgentScheduleRun):
        assert "deleted_at" not in model.__table__.c
        assert "created_at" in model.__table__.c
        assert "updated_at" in model.__table__.c
