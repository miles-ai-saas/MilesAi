"""资源域 · 外包供应商 ORM。"""

import uuid

from sqlalchemy import Float, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class BizSupplier(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """外包供应商——印刷、拍摄、搭建、场务等合作方。"""

    __tablename__ = "biz_suppliers"
    __table_args__ = (
        Index("idx_biz_suppliers_tenant", "tenant_id"),
        Index("idx_biz_suppliers_category", "tenant_id", "category"),
        Index("idx_biz_suppliers_status", "tenant_id", "status"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="other")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    contact_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    bank_account: Mapped[str | None] = mapped_column(String(64), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class BizSupplierContact(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """供应商联系人。"""

    __tablename__ = "biz_supplier_contacts"
    __table_args__ = (
        Index("idx_biz_supplier_contacts_supplier", "tenant_id", "supplier_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    supplier_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str | None] = mapped_column(String(128), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    is_primary: Mapped[bool] = mapped_column(default=False, nullable=False)


class BizProjectSupplier(Base):
    """项目-供应商关联——记录外包分工与合同金额。"""

    __tablename__ = "biz_project_suppliers"
    __table_args__ = (
        Index("idx_biz_ps_tenant", "tenant_id"),
        Index("idx_biz_ps_project", "tenant_id", "project_id"),
        Index("idx_biz_ps_supplier", "tenant_id", "supplier_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    supplier_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    work_package_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    role_description: Mapped[str | None] = mapped_column(String(256), nullable=True)
    contracted_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
