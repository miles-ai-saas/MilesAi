"""租户对平台内置模型的 BYOK 凭证覆盖（model_resolve 合并调用参数）。"""

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class ModelTenantCredential(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """租户为内置模型配置的 BYOK 覆盖。"""

    __tablename__ = "agt_model_tenant_credentials"
    __table_args__ = (
        UniqueConstraint("tenant_id", "model_config_id", name="un_agt_model_tenant_cred"),
        Index("idx_agt_model_tenant_cred_tenant", "tenant_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    model_config_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    api_base: Mapped[str | None] = mapped_column(String(512), nullable=True)
    api_key_encrypted: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
