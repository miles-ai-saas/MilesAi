"""数据访问基类，封装通用 CRUD。"""

from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.common.exceptions import ConflictError, NotFoundError
from app.common.pagination import paginate
from app.common.schema import PageResult
from app.core.soft_delete import append_not_deleted, has_soft_delete, is_marked_deleted, mark_deleted, not_deleted

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """通用 CRUD + 分页；默认排除 deleted_at 非空的软删行。"""

    def __init__(self, db: AsyncSession, model: type[T]) -> None:
        self.db = db
        self.model = model

    def _apply_not_deleted(self, filters: list[ColumnElement[bool]] | None) -> list[ColumnElement[bool]]:
        return append_not_deleted(filters or [], self.model)

    async def get_by_id(self, entity_id: UUID, *, include_deleted: bool = False) -> T | None:
        entity = await self.db.get(self.model, entity_id)
        if entity is None:
            return None
        if not include_deleted and has_soft_delete(self.model) and is_marked_deleted(entity):
            return None
        return entity

    async def get_by_id_or_raise(self, entity_id: UUID, *, label: str | None = None) -> T:
        entity = await self.get_by_id(entity_id)
        if entity is None:
            raise NotFoundError(label or "资源不存在")
        return entity

    async def get_one(self, *filters: ColumnElement[bool], include_deleted: bool = False) -> T | None:
        where = list(filters)
        if not include_deleted:
            where = self._apply_not_deleted(where)
        stmt = select(self.model)
        if where:
            stmt = stmt.where(*where)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def exists(self, *filters: ColumnElement[bool]) -> bool:
        return (await self.get_one(*filters)) is not None

    async def list_page(
        self,
        *,
        page: int = 1,
        size: int = 20,
        filters: list[ColumnElement[bool]] | None = None,
        order_by: Any | None = None,
        options: list[Any] | None = None,
        include_deleted: bool = False,
    ) -> PageResult[T]:
        return await paginate(
            self.db,
            self.model,
            page=page,
            size=size,
            filters=filters,
            order_by=order_by,
            options=options,
            skip_soft_delete_filter=include_deleted,
        )

    async def create(self, **fields: Any) -> T:
        entity = self.model(**fields)
        self.db.add(entity)
        await self.db.flush()
        return entity

    async def update_fields(self, entity: T, data: dict[str, Any]) -> T:
        for key, value in data.items():
            setattr(entity, key, value)
        await self.db.flush()
        return entity

    async def soft_delete(self, entity: T) -> None:
        if is_marked_deleted(entity):
            return
        await mark_deleted(self.db, entity)

    async def ensure_unique(
        self,
        field: ColumnElement,
        value: Any,
        *,
        message: str,
        exclude_id: UUID | None = None,
    ) -> None:
        stmt = select(self.model).where(field == value)
        if has_soft_delete(self.model):
            stmt = stmt.where(not_deleted(self.model))
        if exclude_id is not None:
            stmt = stmt.where(self.model.id != exclude_id)  # type: ignore[attr-defined]
        if (await self.db.execute(stmt)).scalar_one_or_none():
            raise ConflictError(message)
