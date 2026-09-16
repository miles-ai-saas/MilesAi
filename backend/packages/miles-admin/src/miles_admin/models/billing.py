"""运营后台计费 ORM：套餐、账单与明细项。"""

import enum
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Date, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from miles_core.infra.db import Base
from miles_core.models.base import TimestampMixin, UUIDPrimaryKeyMixin


# 账单状态：草稿 / 已出账 / 已支付 / 作废。
class BillStatus(enum.StrEnum):
    DRAFT = "draft"
    ISSUED = "issued"
    PAID = "paid"
    VOID = "void"


class BillingPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """计费套餐定义及各项配额上限。"""

    __tablename__ = "adm_billing_plans"
    __table_args__ = (UniqueConstraint("code", name="uk_adm_billing_plans_code"),)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_monthly: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    max_knowledge_bases: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    max_storage_mb: Mapped[int] = mapped_column(Integer, default=10240, nullable=False)
    max_tokens_monthly: Mapped[int] = mapped_column(BigInteger, default=1_000_000, nullable=False)
    max_agents: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    max_flows: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    features: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class TenantBill(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """租户账期账单，含用量快照与明细项。"""

    __tablename__ = "adm_tenant_bills"
    __table_args__ = (
        Index("idx_adm_tenant_bills_tenant_id", "tenant_id"),
        Index("idx_adm_tenant_bills_plan_id", "plan_id"),
        Index("un_adm_tenant_bills_tenant_id_period", "tenant_id", "period_start", "period_end"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    plan_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    status: Mapped[BillStatus] = mapped_column(
        SAEnum(BillStatus, name="bill_status", values_callable=lambda x: [e.value for e in x]),
        default=BillStatus.DRAFT,
        nullable=False,
    )
    tokens_used: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    storage_used_mb: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    line_items: Mapped[list["BillLineItem"]] = relationship(
        "BillLineItem",
        back_populates="bill",
        foreign_keys="BillLineItem.bill_id",
        primaryjoin="TenantBill.id == BillLineItem.bill_id",
        cascade="all, delete-orphan",
    )


class BillLineItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """账单明细项（订阅月费 / Token 超量 / 存储超量等）。"""

    __tablename__ = "adm_bill_line_items"
    __table_args__ = (Index("idx_adm_bill_line_items_bill_id", "bill_id"),)

    bill_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    item_type: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=1, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=0, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)

    bill: Mapped["TenantBill"] = relationship(
        "TenantBill",
        back_populates="line_items",
        foreign_keys=[bill_id],
        primaryjoin="BillLineItem.bill_id == TenantBill.id",
    )
