"""运营后台风控 ORM：风险事件、IP 黑名单与限流规则。"""

import enum
import uuid

from sqlalchemy import Boolean, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from miles_core.infra.db import Base
from miles_core.models.base import TimestampMixin, UUIDPrimaryKeyMixin


# 风险事件严重级别。
class RiskSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """平台风险事件记录。"""

    __tablename__ = "adm_risk_events"
    __table_args__ = (
        Index("idx_adm_risk_events_tenant_id", "tenant_id"),
        Index("idx_adm_risk_events_user_id", "user_id"),
        Index("un_adm_risk_events_severity_created_at", "severity", "created_at"),
    )

    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[RiskSeverity] = mapped_column(
        SAEnum(RiskSeverity, name="risk_severity", values_callable=lambda x: [e.value for e in x]),
        default=RiskSeverity.MEDIUM,
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class IpBlacklist(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """平台 IP 黑名单。"""

    __tablename__ = "adm_ip_blacklist"
    __table_args__ = (UniqueConstraint("ip_address", name="uk_adm_ip_blacklist_ip_address"),)

    ip_address: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class RateLimitRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """API 路径限流规则。"""

    __tablename__ = "adm_rate_limit_rules"
    __table_args__ = (Index("idx_adm_rate_limit_rules_path_pattern", "path_pattern"),)

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    path_pattern: Mapped[str] = mapped_column(String(255), nullable=False)
    limit_per_minute: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
