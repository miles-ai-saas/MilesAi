"""销售域 · 客户管理 ORM。"""

import uuid

from sqlalchemy import Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.biz.enums import ConfidentialityLevel
from app.infra.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class BizClient(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """客户主体。

    每个租户下客户的顶层实体，代表签约/潜在甲方。一个客户可以有多个项目、合同和联系人。
    confidentiality_level 决定客户数据安全级别，用于权限控制与字段脱敏。
    short_name 用于列表展示与快速检索，如"阿里巴巴"简写为"阿里"。
    """
    __tablename__ = "biz_clients"
    __table_args__ = (
        Index("idx_biz_clients_tenant", "tenant_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)  # 客户全称，对客合同落款使用
    short_name: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 简称/别名，列表与快捷搜索用
    industry: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 行业分类，用于客户画像与报表分组
    confidentiality_level: Mapped[str] = mapped_column(String(32), nullable=False, default=ConfidentialityLevel.NORMAL.value)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class BizClientContact(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """客户联系人。

    每个客户可以有多个联系人，用于沟通、合同签署通知、商机跟进等。
    is_primary 标记主联系人，项目交付与合同流程中默认视为第一沟通对象。
    """
    __tablename__ = "biz_client_contacts"
    __table_args__ = (
        Index("idx_biz_client_contacts_client", "tenant_id", "client_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str | None] = mapped_column(String(128), nullable=True)  # 职务/Title，如"采购经理"
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    is_primary: Mapped[bool] = mapped_column(default=False, nullable=False)  # 是否为该客户的主联系人
