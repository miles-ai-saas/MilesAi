"""全平台软删除：deleted_at 标记，查询默认排除已删记录。"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement


def utc_now() -> datetime:
    """软删时间戳（UTC）。"""
    return datetime.now(timezone.utc)


def has_soft_delete(model: type[Any]) -> bool:
    """模型是否定义 deleted_at 列。"""
    return hasattr(model, "deleted_at")


def not_deleted(model: type[Any]) -> ColumnElement[bool]:
    """SQL 条件：deleted_at IS NULL。"""
    return model.deleted_at.is_(None)  # type: ignore[attr-defined]


def append_not_deleted(filters: list[ColumnElement[bool]], model: type[Any]) -> list[ColumnElement[bool]]:
    if has_soft_delete(model):
        return [*filters, not_deleted(model)]
    return filters


def is_marked_deleted(entity: Any) -> bool:
    return getattr(entity, "deleted_at", None) is not None


async def mark_deleted(db: AsyncSession, entity: Any) -> None:
    """单实体软删并 flush（不 commit，由 get_db 收尾）。"""
    entity.deleted_at = utc_now()
    await db.flush()


async def mark_deleted_where(
    db: AsyncSession,
    model: type[Any],
    *filters: ColumnElement[bool],
) -> None:
    """批量软删（如删除 Hook 时级联 HookBinding）。"""
    if not has_soft_delete(model):
        return
    stmt = update(model).where(*filters, not_deleted(model)).values(deleted_at=utc_now())
    await db.execute(stmt)
