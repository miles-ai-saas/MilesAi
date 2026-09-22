"""BaseRepository.exists / ensure_unique 应使用 EXISTS，不拉整行实体。"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import Column, String
from sqlalchemy.orm import declarative_base

from miles_core.repository import BaseRepository

Base = declarative_base()


class _Row(Base):
    __tablename__ = "repo_row_probe"
    id = Column(String, primary_key=True)
    name = Column(String)
    deleted_at = Column(String, nullable=True)


@pytest.mark.asyncio
async def test_exists_compiles_to_exists_subquery():
    db = AsyncMock()
    captured = {}

    async def _execute(stmt):
        captured["sql"] = str(stmt.compile(compile_kwargs={"literal_binds": False}))
        result = MagicMock()
        result.scalar.return_value = True
        return result

    db.execute = _execute
    repo = BaseRepository(db, _Row)
    assert await repo.exists(_Row.name == "a") is True
    sql = captured["sql"].lower()
    assert "exists" in sql


@pytest.mark.asyncio
async def test_ensure_unique_compiles_to_exists_subquery():
    db = AsyncMock()
    captured = {}

    async def _execute(stmt):
        captured["sql"] = str(stmt.compile(compile_kwargs={"literal_binds": False}))
        result = MagicMock()
        result.scalar.return_value = False
        return result

    db.execute = _execute
    repo = BaseRepository(db, _Row)
    await repo.ensure_unique(_Row.name, "a", message="dup")
    sql = captured["sql"].lower()
    assert "exists" in sql
