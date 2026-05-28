"""ORM 混入：UUIDv7 主键与时间戳/软删列。"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.utils.idgen import generate_uuid


class TimestampMixin:
    """created_at / updated_at / deleted_at（软删：deleted_at 非空即已删）。"""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

    from typing import TYPE_CHECKING

    # 类型注解，用于 IDE 提示
    if TYPE_CHECKING:
        created_at: datetime
        updated_at: datetime


class AuditTimestampMixin:
    """仅 created_at / updated_at，供审计与 append-only 日志表（无软删）。"""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        created_at: datetime
        updated_at: datetime


class UUIDPrimaryKeyMixin:
    """主键默认 UUIDv7（时间有序，见 app.utils.idgen）。"""

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    from typing import TYPE_CHECKING

    # 类型注解，用于 IDE 提示
    if TYPE_CHECKING:
        id: UUID
