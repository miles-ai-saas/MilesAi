"""审计/日志 ORM 与迁移列一致（无 deleted_at）。"""

from miles_core.models.agent.schedule_run import AgentScheduleRun
from miles_core.models.model.usage_log import ModelUsageLog
from miles_portal.tenant.hooks.models import HookExecutionLog


def test_audit_log_models_have_no_deleted_at_column():
    for model in (ModelUsageLog, HookExecutionLog, AgentScheduleRun):
        assert "deleted_at" not in model.__table__.c
        assert "created_at" in model.__table__.c
        assert "updated_at" in model.__table__.c
