"""监控 Service 聚合包。

对外::

    from miles_portal.tenant.monitor.services.monitor import MonitorService, ALERT_CONFIG_KEY, alert_config_key
"""

from miles_portal.tenant.monitor.services.monitor.constants import ALERT_CONFIG_KEY, alert_config_key
from miles_portal.tenant.monitor.services.monitor.service import MonitorService

__all__ = ["ALERT_CONFIG_KEY", "MonitorService", "alert_config_key"]
