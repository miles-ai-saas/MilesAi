"""监控告警配置键。"""

from __future__ import annotations

from uuid import UUID

# 旧全局键（无租户隔离）；读写时优先租户键，读侧兼容回落。
ALERT_CONFIG_KEY = "monitor.alert"


def alert_config_key(tenant_id: UUID) -> str:
    """租户级告警配置键。"""
    return f"{ALERT_CONFIG_KEY}:{tenant_id}"
