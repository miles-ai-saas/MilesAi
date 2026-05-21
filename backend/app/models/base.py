import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.utils.idgen import generate_uuid


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    from typing import TYPE_CHECKING

    # 类型注解，用于 IDE 提示
    if TYPE_CHECKING:
        created_at: datetime
        updated_at: datetime


class UUIDPrimaryKeyMixin:
    """主键默认 UUIDv7（时间有序，见 app.utils.idgen）。"""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    from typing import TYPE_CHECKING

    # 类型注解，用于 IDE 提示
    if TYPE_CHECKING:
        id: UUID
