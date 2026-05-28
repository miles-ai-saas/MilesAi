"""租户用户 ORM（JWT sub、RBAC 经 user_roles）。"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infra.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.role import user_roles

if TYPE_CHECKING:
    from app.models.role import Role
    from app.models.tenant import Tenant


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """username 全局唯一；软删后不可登录。"""

    __tablename__ = "sys_users"
    __table_args__ = (
        Index("idx_sys_users_tenant_id", "tenant_id"),
        UniqueConstraint("username", name="uk_sys_users_username"),
        UniqueConstraint("email", name="uk_sys_users_email"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="users",
        foreign_keys=[tenant_id],
        primaryjoin="User.tenant_id == Tenant.id",
    )
    roles: Mapped[list["Role"]] = relationship(
        "Role",
        secondary=user_roles,
        back_populates="users",
        primaryjoin="User.id == sys_user_roles.c.user_id",
        secondaryjoin="Role.id == sys_user_roles.c.role_id",
    )
