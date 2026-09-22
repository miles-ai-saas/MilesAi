"""数据访问基类，封装通用 CRUD。"""

from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from miles_common.exceptions import ConflictError, NotFoundError
from miles_common.schema import PageResult
from miles_core.pagination import paginate
from miles_core.soft_delete import append_not_deleted, has_soft_delete, is_marked_deleted, mark_deleted, not_deleted

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """通用 CRUD + 分页；默认排除 deleted_at 非空的软删行。"""

    def __init__(self, db: AsyncSession, model: type[T]) -> None:
        self.db = db
        self.model = model

    def _apply_not_deleted(self, filters: list[ColumnElement[bool]] | None) -> list[ColumnElement[bool]]:
        return append_not_deleted(filters or [], self.model)

    async def get_by_id(self, entity_id: UUID, *, include_deleted: bool = False) -> T | None:
        """按主键查询；默认把软删行视为不存在（``include_deleted=True`` 可覆盖）。"""
        entity = await self.db.get(self.model, entity_id)
        if entity is None:
            return None
        if not include_deleted and has_soft_delete(self.model) and is_marked_deleted(entity):
            return None
        return entity

    async def get_by_id_or_raise(self, entity_id: UUID, *, label: str | None = None) -> T:
        """同 ``get_by_id``，未命中抛 ``NotFoundError``（``label`` 自定义文案）。"""
        entity = await self.get_by_id(entity_id)
        if entity is None:
            raise NotFoundError(label or "资源不存在")
        return entity

    async def get_one(self, *filters: ColumnElement[bool], include_deleted: bool = False) -> T | None:
        """按条件查询首条记录；默认过滤软删行。"""
        where = list(filters)
        if not include_deleted:
            where = self._apply_not_deleted(where)
        stmt = select(self.model)
        if where:
            stmt = stmt.where(*where)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def exists(self, *filters: ColumnElement[bool]) -> bool:
        """是否存在满足条件的未删除记录（不加载实体）。"""
        where = self._apply_not_deleted(list(filters))
        stmt = select(exists(select(1).select_from(self.model).where(*where))) if where else select(
            exists(select(1).select_from(self.model))
        )
        return bool((await self.db.execute(stmt)).scalar())

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
        """分页查询并返回 ``PageResult``；默认排除软删行。"""
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
        """实例化模型并 flush（不 commit；主键在 flush 后可用）。"""
        entity = self.model(**fields)
        self.db.add(entity)
        await self.db.flush()
        return entity

    async def update_fields(self, entity: T, data: dict[str, Any]) -> T:
        """按 dict 批量 ``setattr`` 并 flush（不 commit）。"""
        for key, value in data.items():
            setattr(entity, key, value)
        await self.db.flush()
        return entity

    async def soft_delete(self, entity: T) -> None:
        """写入 ``deleted_at`` 并 flush；已软删则直接返回（幂等）。"""
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
        """校验 ``field == value`` 未被占用；冲突抛 ``ConflictError``。

        软删行不参与校验，``exclude_id`` 用于更新时排除自身。
        """
        clauses: list[ColumnElement[bool]] = [field == value]
        if has_soft_delete(self.model):
            clauses.append(not_deleted(self.model))
        if exclude_id is not None:
            id_col = getattr(self.model, "id", None)
            if id_col is not None:
                clauses.append(id_col != exclude_id)
        stmt = select(exists(select(1).select_from(self.model).where(*clauses)))
        if (await self.db.execute(stmt)).scalar():
            raise ConflictError(message)
