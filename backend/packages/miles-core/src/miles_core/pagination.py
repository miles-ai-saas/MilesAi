"""分页查询通用逻辑。"""

from typing import Any, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from miles_common.schema import PageParams, PageResult
from miles_core.soft_delete import append_not_deleted

T = TypeVar("T")


async def paginate(
    db: AsyncSession,
    model: type[T],
    *,
    page: int = 1,
    size: int = 20,
    filters: list[ColumnElement[bool]] | None = None,
    order_by: Any | None = None,
    options: list[Any] | None = None,
    skip_soft_delete_filter: bool = False,
) -> PageResult[T]:
    """对单表执行 count + 分页查询。"""
    params = PageParams(page=page, size=size)
    where = list(filters or [])
    if not skip_soft_delete_filter:
        where = append_not_deleted(where, model)

    count_stmt = select(func.count(model.id))
    if where:
        count_stmt = count_stmt.where(*where)
    total = int((await db.execute(count_stmt)).scalar() or 0)

    stmt: Select[tuple[T]] = select(model)
    if options:
        stmt = stmt.options(*options)
    if where:
        stmt = stmt.where(*where)
    if order_by is not None:
        stmt = stmt.order_by(order_by)
    stmt = stmt.offset(params.offset).limit(params.size)

    rows = (await db.execute(stmt)).scalars().all()
    return PageResult(items=list(rows), total=total, page=params.page, size=params.size)
