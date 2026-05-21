import uuid

from sqlalchemy import Boolean, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class SkillPackage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "skl_skill_packages"
    __table_args__ = (
        Index("idx_skl_skill_packages_tenant_id", "tenant_id"),
        Index("un_skl_skill_packages_tenant_id_name", "tenant_id", "name"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_names: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    prompt_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
