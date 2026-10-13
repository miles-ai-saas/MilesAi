"""租户运行监控：资源统计、任务趋势、依赖健康与告警 Webhook。

子模块：``report`` / ``alerts``；对外 ``from …services.monitor import MonitorService``。
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.tenant import TenantContext
from miles_portal.tenant.monitor.services.monitor.alerts import MonitorAlertsMixin
from miles_portal.tenant.monitor.services.monitor.report import MonitorReportMixin


class MonitorService(MonitorAlertsMixin, MonitorReportMixin):
    """工作台监控页：租户资源统计、Celery 任务趋势、健康检查与告警配置。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        MonitorReportMixin.__init__(self, db, ctx)
