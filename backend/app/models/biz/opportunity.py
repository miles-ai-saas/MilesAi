"""销售域 · 商机漏斗 ORM。"""

import uuid

from sqlalchemy import Date, Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class BizOpportunity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """商机。

    销售流水线核心实体，代表潜在项目机会。按 stage 推进销售阶段，如 prospecting → qualification → proposal → negotiation → closed_won / closed_lost。
    expected_value 为预估合同金额，probability 为成单概率（0-100），二者乘积得出加权商机金额，用于销售漏斗预测。
    converted_to_project_id 标识商机转化后的项目，实现"商机→项目"的一对一转化闭环。
    """
    __tablename__ = "biz_opportunities"
    __table_args__ = (
        Index("idx_biz_opp_tenant", "tenant_id"),
        Index("idx_biz_opp_client", "tenant_id", "client_id"),
        Index("idx_biz_opp_stage", "tenant_id", "stage"),
        Index("idx_biz_opp_owner", "tenant_id", "owner_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    code: Mapped[str | None] = mapped_column(String(32), nullable=True)  # 商机编号
    stage: Mapped[str] = mapped_column(String(32), nullable=False, default="prospecting")  # 销售阶段: prospecting → qualification → proposal → negotiation → closed_won/closed_lost
    expected_value: Mapped[float | None] = mapped_column(Float, nullable=True)  # 预估合同金额
    probability: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 成单概率 0-100，与 expected_value 组合计算加权金额
    expected_close_date: Mapped[str | None] = mapped_column(Date, nullable=True)  # 预计关单日期
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)  # 商机负责人
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    converted_to_project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)  # 转化后的项目ID，非空表示已转化
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
