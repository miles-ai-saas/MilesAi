"""Alembic 迁移辅助：兼容 001(create_all) 与增量迁移并存。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


def _insp():
    return inspect(op.get_bind())


def table_exists(name: str) -> bool:
    return _insp().has_table(name)


def column_exists(table: str, column: str) -> bool:
    if not table_exists(table):
        return False
    return column in {c["name"] for c in _insp().get_columns(table)}


def index_exists(table: str, name: str) -> bool:
    if not table_exists(table):
        return False
    return name in {i["name"] for i in _insp().get_indexes(table)}


def add_column_if_missing(table: str, column: sa.Column) -> None:
    if not column_exists(table, column.name):
        op.add_column(table, column)


def create_index_if_missing(name: str, table: str, columns: list[str], **kw) -> None:
    if not index_exists(table, name):
        op.create_index(name, table, columns, **kw)
