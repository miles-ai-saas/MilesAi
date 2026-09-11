"""模型配置 ORM（租户自定义 + 平台内置 tenant_id=NULL）。

对话走 litellm_chat_completion；embedding/rerank 见 integrations 各 provider。
"""

import uuid

from sqlalchemy import Boolean, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from miles_core.infra.db import Base
from miles_core.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from miles_core.models.model.catalog import ModelCapabilityType, ModelPublishStatus, ModelVendor


class ModelConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """api_key_encrypted 明文存储（一期）；extra 可含 litellm_model 覆盖。"""

    __tablename__ = "agt_model_configs"
    __table_args__ = (
        Index("idx_agt_model_configs_tenant_id", "tenant_id"),
        Index("idx_agt_model_configs_vendor", "vendor"),
        Index("idx_agt_model_configs_publish", "publish_status"),
    )

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    vendor: Mapped[str] = mapped_column(String(32), default=ModelVendor.OTHER.value, nullable=False)
    model_type: Mapped[str] = mapped_column(String(32), default=ModelCapabilityType.LLM.value, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_window: Mapped[str | None] = mapped_column(String(32), nullable=True)
    capabilities: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    publish_status: Mapped[str] = mapped_column(String(16), default=ModelPublishStatus.PUBLISHED.value, nullable=False)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    badge: Mapped[str | None] = mapped_column(String(16), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    api_base: Mapped[str | None] = mapped_column(String(512), nullable=True)
    api_key_encrypted: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    extra: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    @property
    def source(self) -> str:
        """来源标识：``tenant_id`` 为空即平台内置，否则租户自定义。"""
        return "builtin" if self.tenant_id is None else "custom"

    @property
    def is_builtin(self) -> bool:
        """是否平台内置（无租户归属）。"""
        return self.tenant_id is None
