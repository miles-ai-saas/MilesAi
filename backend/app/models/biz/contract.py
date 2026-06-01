"""财务域 · 合同与收付款 ORM。"""

import uuid

from sqlalchemy import Date, Float, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class BizContract(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """合同。

    项目签约的法律主体文件，记录合同金额、起止日期、付款条款等关键商业条款。
    type 区分合同类型（service 服务合同 / procurement 采购合同等），status 流转：draft → signed → active → expired / terminated。
    payment_terms 记录分期付款节点描述；total_amount 为合同总金额，用于收入确认与回款追踪。
    """
    __tablename__ = "biz_contracts"
    __table_args__ = (
        Index("idx_biz_ctr_tenant", "tenant_id"),
        Index("idx_biz_ctr_project", "tenant_id", "project_id"),
        Index("idx_biz_ctr_client", "tenant_id", "client_id"),
        Index("idx_biz_ctr_status", "tenant_id", "status"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    contract_no: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 合同编号，对客落款时的正式编号
    type: Mapped[str] = mapped_column(String(32), nullable=False, default="service")  # 合同类型: service 服务合同 / procurement 采购合同
    signed_date: Mapped[str | None] = mapped_column(Date, nullable=True)  # 签署日期
    start_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    total_amount: Mapped[float | None] = mapped_column(Float, nullable=True)  # 合同总金额
    payment_terms: Mapped[str | None] = mapped_column(String(256), nullable=True)  # 付款条款，如"签约付30%，验收付70%"
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")  # draft → signed → active → expired / terminated
    attachment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)  # 合同附件，指向已上传的合同文件
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class BizPayment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """合同收付款记录。

    记录合同执行过程中的每笔收/付款项，用于现金流追踪与回款预警。
    direction 区分收款(in)与付款(out)；status 流转：pending → paid，表示计划→实际到账。
    planned_date 为计划收付日期，paid_date 为实际发生日期，二者对比用于回款偏差分析。
    method 标识支付方式（银行转账/支票/现金等），用于财务核算。
    """

    __tablename__ = "biz_payments"
    __table_args__ = (
        Index("idx_biz_pay_tenant", "tenant_id"),
        Index("idx_biz_pay_contract", "tenant_id", "contract_id"),
        Index("idx_biz_pay_project", "tenant_id", "project_id"),
        Index("idx_biz_pay_status", "tenant_id", "status"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    contract_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False, default="in")  # in=收款(甲方→我方), out=付款(我方→供应商)
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    planned_date: Mapped[str | None] = mapped_column(Date, nullable=True)  # 计划收付日期
    paid_date: Mapped[str | None] = mapped_column(Date, nullable=True)  # 实际到账日期，与 planned_date 对比用于回款偏差分析
    method: Mapped[str | None] = mapped_column(String(32), nullable=True)  # 支付方式: 银行转账/支票/现金等
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")  # pending → paid
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
