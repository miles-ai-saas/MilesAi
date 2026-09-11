"""模型调用用量日志（agt_model_usage_logs）。"""

import uuid

from sqlalchemy import Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from miles_core.infra.db import Base
from miles_core.models.base import AuditTimestampMixin, UUIDPrimaryKeyMixin


class ModelUsageLog(UUIDPrimaryKeyMixin, AuditTimestampMixin, Base):
    """模型调用 token 用量流水（供计量与配额）。"""

    __tablename__ = "agt_model_usage_logs"
    __table_args__ = (
        Index("idx_agt_model_usage_logs_tenant_id", "tenant_id"),
        Index("idx_agt_model_usage_logs_model_id", "model_config_id"),
        Index("idx_agt_model_usage_logs_created_at", "created_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    model_config_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="chat", nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
