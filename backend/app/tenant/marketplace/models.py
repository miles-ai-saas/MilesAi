"""应用市场 ORM：分类、应用包、安装记录与评分。"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infra.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class MarketplaceAppStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    PUBLISHED = "published"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class MarketplaceAppVisibility(str, enum.Enum):
    PUBLIC = "public"
    TENANT_ONLY = "tenant_only"


class AppCategory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "mkt_categories"
    __table_args__ = (UniqueConstraint("slug", name="uk_mkt_categories_slug"),)

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class MarketplaceApp(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """市场应用包；manifest JSON 描述可安装的 KB/Flow/Agent 快照。"""

    __tablename__ = "mkt_apps"
    __table_args__ = (
        Index("idx_mkt_apps_publisher_tenant_id", "publisher_tenant_id"),
        Index("idx_mkt_apps_category_id", "category_id"),
        Index("idx_mkt_apps_status", "status"),
    )

    publisher_tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str | None] = mapped_column(String(32), nullable=True)
    version: Mapped[str] = mapped_column(String(32), default="1.0.0", nullable=False)
    status: Mapped[MarketplaceAppStatus] = mapped_column(
        SAEnum(
            MarketplaceAppStatus,
            name="marketplace_app_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=MarketplaceAppStatus.PUBLISHED,
        nullable=False,
    )
    is_official: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    install_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    manifest: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    rating_avg: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rating_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    visibility: Mapped[str] = mapped_column(String(32), default="public", nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    category: Mapped["AppCategory | None"] = relationship(
        "AppCategory",
        foreign_keys=[category_id],
        primaryjoin="MarketplaceApp.category_id == AppCategory.id",
    )
    installs: Mapped[list["AppInstall"]] = relationship(
        "AppInstall",
        back_populates="app",
        foreign_keys="AppInstall.app_id",
        primaryjoin="MarketplaceApp.id == AppInstall.app_id",
    )
    ratings: Mapped[list["AppRating"]] = relationship(
        "AppRating",
        back_populates="app",
        foreign_keys="AppRating.app_id",
        primaryjoin="MarketplaceApp.id == AppRating.app_id",
    )


class AppRating(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "mkt_ratings"
    __table_args__ = (
        Index("idx_mkt_ratings_app_id", "app_id"),
        Index("idx_mkt_ratings_tenant_id", "tenant_id"),
        UniqueConstraint("tenant_id", "app_id", "user_id", name="uk_mkt_ratings_tenant_app_user"),
    )

    app_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    app: Mapped["MarketplaceApp"] = relationship(
        "MarketplaceApp",
        back_populates="ratings",
        foreign_keys=[app_id],
        primaryjoin="AppRating.app_id == MarketplaceApp.id",
    )


class AppInstall(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """租户安装记录；指向本租户克隆出的 flow_id/agent_id/kb_id。"""

    __tablename__ = "mkt_installs"
    __table_args__ = (
        Index("idx_mkt_installs_tenant_id", "tenant_id"),
        Index("idx_mkt_installs_app_id", "app_id"),
        UniqueConstraint("tenant_id", "app_id", name="uk_mkt_installs_tenant_id_app_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    app_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    installed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    installed_version: Mapped[str] = mapped_column(String(32), default="1.0.0", nullable=False)
    flow_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    kb_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    app: Mapped["MarketplaceApp"] = relationship(
        "MarketplaceApp",
        back_populates="installs",
        foreign_keys=[app_id],
        primaryjoin="AppInstall.app_id == MarketplaceApp.id",
    )
