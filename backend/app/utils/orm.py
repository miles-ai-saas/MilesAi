"""ORM 约定：逻辑外键（无 DB FK）+ 显式索引命名。

- idx_* 普通索引
- uk_* 唯一索引/约束
- un_* 联合索引（非唯一）
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


def ref_uuid(*, nullable: bool = False) -> Mapped[uuid.UUID | None]:
    """逻辑外键 UUID 列，不创建数据库级 ForeignKey。"""
    return mapped_column(UUID(as_uuid=True), nullable=nullable)


def idx(name: str, *columns: str) -> Index:
    """普通索引 ``idx_*``。"""
    return Index(name, *columns)


def uk(name: str, *columns: str) -> UniqueConstraint:
    """唯一约束 ``uk_*``。"""
    return UniqueConstraint(*columns, name=name)


def un(name: str, *columns: str) -> Index:
    """联合索引（非唯一）。"""
    return Index(name, *columns)


def rel_foreign_keys(*columns: Any) -> list[Any]:
    """relationship(foreign_keys=...) 简写。"""
    return list(columns)
