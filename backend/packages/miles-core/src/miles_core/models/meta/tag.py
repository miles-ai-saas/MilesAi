"""租户全局标签 ORM（tnt_tags、tnt_entity_tag_bindings）。

标签在租户内跨智能体/提示词/技能/工具/流程共用；与 ``sys_categories`` 的系统预置分类互补：
分类负责稳定导航（单选），标签负责用户自定义标记（多选）。
"""

import enum
import uuid

from sqlalchemy import Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from miles_core.infra.db import Base
from miles_core.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class TagEntityType(enum.StrEnum):
    """绑定表 entity_type 取值，与各业务表主键对应。"""

    AGENT = "agent"
    PROMPT = "prompt"
    SKILL = "skill"
    TOOL = "tool"
    FLOW = "flow"
    MARKETPLACE_APP = "marketplace_app"


class TenantTag(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """租户标签定义；``(tenant_id, slug)`` 唯一。"""

    __tablename__ = "tnt_tags"
    __table_args__ = (
        Index("uk_tnt_tags_tenant_slug", "tenant_id", "slug", unique=True),
        Index("idx_tnt_tags_tenant_id", "tenant_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False)


class EntityTagBinding(UUIDPrimaryKeyMixin, Base):
    """资源 ↔ 标签多对多；删除标签或资源时需清理对应行。"""

    __tablename__ = "tnt_entity_tag_bindings"
    __table_args__ = (
        Index(
            "uk_tnt_entity_tag_bindings",
            "entity_type",
            "entity_id",
            "tag_id",
            unique=True,
        ),
        Index("idx_tnt_entity_tag_bindings_tenant", "tenant_id", "entity_type", "entity_id"),
        Index("idx_tnt_entity_tag_bindings_tag", "tenant_id", "tag_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    tag_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
