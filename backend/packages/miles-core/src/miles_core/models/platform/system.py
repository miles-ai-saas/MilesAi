"""平台系统配置键值 ORM（sys_configs）。"""

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from miles_core.infra.db import Base
from miles_core.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class SystemConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """系统配置项；``key`` 唯一，``value`` 以 JSONB 存储。"""

    __tablename__ = "sys_configs"
    __table_args__ = (UniqueConstraint("key", name="uk_sys_configs_key"),)

    key: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_encrypted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
