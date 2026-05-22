from sqlalchemy import Boolean, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class PlatformAdmin(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "adm_admins"
    __table_args__ = (UniqueConstraint("username", name="uk_adm_admins_username"),)

    username: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="operator", nullable=False)
