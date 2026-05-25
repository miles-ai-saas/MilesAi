"""技能包 ORM：元数据入库，正文与附属文件见 storage（按 tenant_id/slug 落盘）。"""

import uuid

from sqlalchemy import Boolean, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class SkillPackage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """租户技能包一行记录；与磁盘目录 `{skills_data_root}/{tenant_id}/{slug}/` 一一对应。"""

    __tablename__ = "skl_skill_packages"
    __table_args__ = (
        Index("idx_skl_skill_packages_tenant_id", "tenant_id"),
        Index("idx_skl_skill_packages_category", "tenant_id", "category_id"),
        Index("idx_skl_skill_packages_tenant_name", "tenant_id", "name"),
        UniqueConstraint("tenant_id", "slug", name="uk_skl_skill_packages_tenant_slug"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )  # sys_categories.domain=skill
    slug: Mapped[str] = mapped_column(String(128), nullable=False)  # 磁盘子目录名，租户内唯一
    name: Mapped[str] = mapped_column(String(128), nullable=False)  # 展示名，常来自 SKILL.md frontmatter
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(
        String(32), default="manual", nullable=False
    )  # manual | local | zip | git
    storage_path: Mapped[str | None] = mapped_column(
        String(512), nullable=True
    )  # 相对存储标识，默认与 slug 相同
    tool_names: Mapped[list] = mapped_column(
        JSONB, default=list, nullable=False
    )  # 遗留：旧版表单勾选的工具名，注入时可选追加
    prompt_snippet: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # 无磁盘 SKILL.md 时供 agents.context 回退
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
