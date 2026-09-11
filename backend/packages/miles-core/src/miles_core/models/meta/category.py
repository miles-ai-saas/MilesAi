"""工作台分类 sys_categories ORM（全平台全局字典）。

全租户共用同一套分类 ID；运营维护，租户 API 只读。个性化组织使用 ``tnt_tags``。
与 ``mkt_categories``（应用市场）职责分离。
"""

import enum
import uuid

from sqlalchemy import Boolean, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from miles_core.infra.db import Base
from miles_core.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class CategoryDomain(str, enum.Enum):
    """工作台资源域；与列表 Tab、校验时的 domain 参数一致。"""

    AGENT = "agent"
    PROMPT = "prompt"
    SKILL = "skill"
    TOOL = "tool"


class SysCategory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """系统预置分类（粗粒度导航，资源上为单选 category_id）。"""

    __tablename__ = "sys_categories"
    __table_args__ = (
        Index("uk_sys_categories_domain_slug", "domain", "slug", unique=True),
        Index("idx_sys_categories_domain", "domain"),
    )

    domain: Mapped[str] = mapped_column(String(32), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
