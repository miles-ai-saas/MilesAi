"""initial schema (domain-prefixed tables, no DB foreign keys)

Revision ID: 001
Revises:
Create Date: 2026-05-21

表结构与索引以各 ORM 模型的 __tablename__ / __table_args__ 为准；
本迁移通过 metadata.create_all 一次性建表（逻辑外键，无数据库 FK）。

"""

from typing import Sequence, Union

from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.core.database import Base
    from app.models.registry import load_all_models

    load_all_models()
    bind = op.get_bind()
    Base.metadata.create_all(bind)


def downgrade() -> None:
    from app.core.database import Base
    from app.models.registry import load_all_models

    load_all_models()
    bind = op.get_bind()
    Base.metadata.drop_all(bind)
