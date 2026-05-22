import enum
import uuid

from sqlalchemy import Boolean, Index, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class SensitiveAction(str, enum.Enum):
    WARN = "warn"
    BLOCK = "block"


class SensitiveWord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cmp_sensitive_words"
    __table_args__ = (
        Index("idx_cmp_sensitive_words_tenant_id", "tenant_id"),
        Index("un_cmp_sensitive_words_tenant_id_word", "tenant_id", "word"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    word: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action: Mapped[SensitiveAction] = mapped_column(
        SAEnum(SensitiveAction, name="sensitive_action", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class InterceptLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cmp_intercept_logs"
    __table_args__ = (
        Index("idx_cmp_intercept_logs_tenant_id", "tenant_id"),
        Index("idx_cmp_intercept_logs_user_id", "user_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    module: Mapped[str] = mapped_column(String(64), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    matched_word: Mapped[str | None] = mapped_column(String(128), nullable=True)
    action: Mapped[SensitiveAction] = mapped_column(
        SAEnum(SensitiveAction, name="sensitive_action", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    content_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
