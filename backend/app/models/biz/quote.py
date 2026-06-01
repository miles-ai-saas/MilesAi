"""销售域 · 商机报价 ORM。"""

import uuid

from sqlalchemy import Date, Float, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class BizQuote(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """报价单——关联商机与客户，支持版本与状态流转。"""

    __tablename__ = "biz_quotes"
    __table_args__ = (
        Index("idx_biz_quotes_tenant", "tenant_id"),
        Index("idx_biz_quotes_opp", "tenant_id", "opportunity_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    valid_until: Mapped[str | None] = mapped_column(Date, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
