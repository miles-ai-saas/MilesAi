"""租户 ORM：套餐配额与用量计数（quota 服务读写 max_* / storage_used_mb）。"""

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from miles_core.infra.db import Base
from miles_core.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from miles_core.models.platform.user import User


# 租户状态。
class TenantStatus(enum.StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TRIAL = "trial"


class Tenant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """多租户隔离根实体；plan_id 关联运营端 BillingPlan。"""

    __tablename__ = "sys_tenants"
    __table_args__ = (
        UniqueConstraint("name", name="uk_sys_tenants_name"),
        Index("idx_sys_tenants_plan_id", "plan_id"),
        Index("idx_sys_tenants_status", "status"),
    )

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    plan_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[TenantStatus] = mapped_column(
        SAEnum(TenantStatus, name="tenant_status", values_callable=lambda x: [e.value for e in x]),
        default=TenantStatus.ACTIVE,
        nullable=False,
    )
    max_knowledge_bases: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    max_storage_mb: Mapped[int] = mapped_column(Integer, default=10240, nullable=False)
    max_tokens_monthly: Mapped[int] = mapped_column(BigInteger, default=1_000_000, nullable=False)
    max_agents: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    max_flows: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    tokens_used_month: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    storage_used_mb: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="tenant",
        foreign_keys="User.tenant_id",
        primaryjoin="Tenant.id == User.tenant_id",
    )
