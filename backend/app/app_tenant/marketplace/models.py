import enum
import uuid

from sqlalchemy import Boolean, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class MarketplaceAppStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class AppCategory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "mkt_categories"
    __table_args__ = (UniqueConstraint("slug", name="uk_mkt_categories_slug"),)

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class MarketplaceApp(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "mkt_apps"
    __table_args__ = (
        Index("idx_mkt_apps_publisher_tenant_id", "publisher_tenant_id"),
        Index("idx_mkt_apps_category_id", "category_id"),
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


class AppInstall(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "mkt_installs"
    __table_args__ = (
        Index("idx_mkt_installs_tenant_id", "tenant_id"),
        Index("idx_mkt_installs_app_id", "app_id"),
        UniqueConstraint("tenant_id", "app_id", name="uk_mkt_installs_tenant_id_app_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    app_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    installed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    flow_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    kb_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    app: Mapped["MarketplaceApp"] = relationship(
        "MarketplaceApp",
        back_populates="installs",
        foreign_keys=[app_id],
        primaryjoin="AppInstall.app_id == MarketplaceApp.id",
    )
