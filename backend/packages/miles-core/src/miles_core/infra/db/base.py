"""SQLAlchemy 声明基类。"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """所有 ORM 模型的 SQLAlchemy 声明基类。"""
