"""数据访问基类，封装通用 CRUD。"""

from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.common.exceptions import ConflictError, NotFoundError
from app.common.pagination import paginate
from app.common.schema import PageResult

T = TypeVar("T")


class BaseRepository(Generic[T]):
    def __init__(self, db: AsyncSession, model: type[T]) -> None:
        self.db = db
        self.model = model

    async def get_by_id(self, entity_id: UUID) -> T | None:
        return await self.db.get(self.model, entity_id)

    async def get_by_id_or_raise(self, entity_id: UUID, *, label: str | None = None) -> T:
        entity = await self.get_by_id(entity_id)
        if entity is None:
            raise NotFoundError(label or "资源不存在")
        return entity

    async def get_one(self, *filters: ColumnElement[bool]) -> T | None:
        stmt = select(self.model)
        if filters:
            stmt = stmt.where(*filters)
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
    ) -> PageResult[T]:
        return await paginate(
            self.db,
            self.model,
            page=page,
            size=size,
            filters=filters,
            order_by=order_by,
            options=options,
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

    async def ensure_unique(
        self,
        field: ColumnElement,
        value: Any,
        *,
        message: str,
        exclude_id: UUID | None = None,
    ) -> None:
        stmt = select(self.model).where(field == value)
        if exclude_id is not None:
            stmt = stmt.where(self.model.id != exclude_id)  # type: ignore[attr-defined]
        if (await self.db.execute(stmt)).scalar_one_or_none():
            raise ConflictError(message)
