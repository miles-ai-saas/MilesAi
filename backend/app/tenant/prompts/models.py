"""提示词模板 ORM（prm_prompt_templates）。"""

import uuid

from sqlalchemy import Boolean, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class PromptTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """可复用 system/user 片段；Agent 创建时可拷贝 content。"""

    __tablename__ = "prm_prompt_templates"
    __table_args__ = (
        Index("idx_prm_prompt_templates_tenant_id", "tenant_id"),
        Index("un_prm_prompt_templates_tenant_id_name", "tenant_id", "name"),
        Index("idx_prm_prompt_templates_category_id", "category_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    category_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(256), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
