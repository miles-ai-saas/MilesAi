"""全平台软删除：deleted_at 标记，查询默认排除已删记录。"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def has_soft_delete(model: type[Any]) -> bool:
    return hasattr(model, "deleted_at")


def not_deleted(model: type[Any]) -> ColumnElement[bool]:
    return model.deleted_at.is_(None)  # type: ignore[attr-defined]


def append_not_deleted(filters: list[ColumnElement[bool]], model: type[Any]) -> list[ColumnElement[bool]]:
    if has_soft_delete(model):
        return [*filters, not_deleted(model)]
    return filters


def is_marked_deleted(entity: Any) -> bool:
    return getattr(entity, "deleted_at", None) is not None


async def mark_deleted(db: AsyncSession, entity: Any) -> None:
    entity.deleted_at = utc_now()
    await db.flush()


async def mark_deleted_where(
    db: AsyncSession,
    model: type[Any],
    *filters: ColumnElement[bool],
) -> None:
    if not has_soft_delete(model):
        return
    stmt = (
        update(model)
        .where(*filters, not_deleted(model))
        .values(deleted_at=utc_now())
    )
    await db.execute(stmt)
