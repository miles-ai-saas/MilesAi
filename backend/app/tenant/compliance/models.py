"""合规：词库、词条、库-词关联、租户扫描绑定、拦截日志。"""

import uuid

from sqlalchemy import Boolean, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.compliance.constants import SensitiveAction

DEFAULT_WORD_LIBRARY_NAME = "默认词库"
COMPLIANCE_SCOPE_TENANT = "tenant"


_sensitive_action_enum = SAEnum(
    SensitiveAction,
    name="sensitive_action",
    values_callable=lambda x: [e.value for e in x],
)


class WordLibrary(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """租户内敏感词库；同一租户下名称唯一。"""

    __tablename__ = "cmp_word_libraries"
    __table_args__ = (
        Index("idx_cmp_word_libraries_tenant_id", "tenant_id"),
        UniqueConstraint("tenant_id", "name", name="un_cmp_word_libraries_tenant_name"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class SensitiveWordEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """租户内词条（词面唯一）；通过 binding 关联多个词库。"""

    __tablename__ = "cmp_sensitive_word_entries"
    __table_args__ = (
        Index("idx_cmp_sensitive_word_entries_tenant_id", "tenant_id"),
        UniqueConstraint("tenant_id", "word", name="un_cmp_sensitive_word_entries_tenant_word"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    word: Mapped[str] = mapped_column(String(128), nullable=False)


class LibraryWordBinding(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """词库-词条绑定；记录该词在指定词库内的处理策略与启用态。"""

    __tablename__ = "cmp_library_word_bindings"
    __table_args__ = (
        Index("idx_cmp_library_word_bindings_library_id", "library_id"),
        Index("idx_cmp_library_word_bindings_entry_id", "entry_id"),
        UniqueConstraint("library_id", "entry_id", name="un_cmp_library_word_bindings_lib_entry"),
    )

    library_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entry_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[SensitiveAction] = mapped_column(_sensitive_action_enum, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ComplianceLibraryBinding(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """租户级：哪些词库参与合规扫描（未绑定则不扫描）。"""

    __tablename__ = "cmp_compliance_library_bindings"
    __table_args__ = (
        Index("idx_cmp_compliance_library_bindings_tenant_id", "tenant_id"),
        UniqueConstraint(
            "tenant_id",
            "library_id",
            "scope",
            name="un_cmp_compliance_library_bindings_tenant_lib_scope",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    library_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scope: Mapped[str] = mapped_column(String(32), nullable=False, default=COMPLIANCE_SCOPE_TENANT)


class InterceptLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """合规拦截日志；记录命中词、动作与内容摘要，供审计追溯。"""

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
    action: Mapped[SensitiveAction] = mapped_column(_sensitive_action_enum, nullable=False)
    content_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
