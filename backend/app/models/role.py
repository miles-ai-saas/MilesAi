import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, Index, String, Table, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infra.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User

user_roles = Table(
    "sys_user_roles",
    Base.metadata,
    Column("user_id", UUID(as_uuid=True), primary_key=True),
    Column("role_id", UUID(as_uuid=True), primary_key=True),
    Index("un_sys_user_roles_user_id_role_id", "user_id", "role_id"),
)

role_permissions = Table(
    "sys_role_permissions",
    Base.metadata,
    Column("role_id", UUID(as_uuid=True), primary_key=True),
    Column("permission_id", UUID(as_uuid=True), primary_key=True),
    Index("un_sys_role_permissions_role_id_permission_id", "role_id", "permission_id"),
)


class Role(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sys_roles"
    __table_args__ = (
        Index("idx_sys_roles_tenant_id", "tenant_id"),
        Index("idx_sys_roles_code", "code"),
    )

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    permissions: Mapped[list["Permission"]] = relationship(
        "Permission",
        secondary=role_permissions,
        back_populates="roles",
        primaryjoin="Role.id == sys_role_permissions.c.role_id",
        secondaryjoin="Permission.id == sys_role_permissions.c.permission_id",
    )
    users: Mapped[list["User"]] = relationship(
        "User",
        secondary=user_roles,
        back_populates="roles",
        primaryjoin="Role.id == sys_user_roles.c.role_id",
        secondaryjoin="User.id == sys_user_roles.c.user_id",
    )


class Permission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sys_permissions"
    __table_args__ = (
        UniqueConstraint("code", name="uk_sys_permissions_code"),
        Index("idx_sys_permissions_module", "module"),
    )

    code: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    module: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    roles: Mapped[list["Role"]] = relationship(
        "Role",
        secondary=role_permissions,
        back_populates="permissions",
        primaryjoin="Permission.id == sys_role_permissions.c.permission_id",
        secondaryjoin="Role.id == sys_role_permissions.c.role_id",
    )
