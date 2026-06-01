"""服务线模板市场 · 可安装模板包 ORM。"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.biz.template_pack_status import TemplatePackStatus


class BizServiceLineTemplatePack(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """服务线模板市场条目。

    每条记录为某服务线的一套可选阶段流水线 + AI 配置，租户「应用」后写入
    ``biz_service_line_templates`` 租户覆盖行。
    ``tenant_id`` 为 NULL 表示平台官方/合作伙伴发布。
    """

    __tablename__ = "biz_service_line_template_packs"
    __table_args__ = (
        Index("idx_biz_sltp_service_line", "service_line"),
        Index("idx_biz_sltp_active", "is_active"),
        Index("idx_biz_sltp_status", "status"),
    )

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    service_line: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    stages: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    ai_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    publisher_name: Mapped[str] = mapped_column(String(128), nullable=False, default="Miles 官方")
    publisher_type: Mapped[str] = mapped_column(String(32), nullable=False, default="platform")
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    install_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=TemplatePackStatus.PUBLISHED.value)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
