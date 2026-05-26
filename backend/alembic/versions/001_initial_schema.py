"""全量初始 schema（唯一迁移，按当前 ORM 一次性建表）

Revision ID: 001
Revises:
Create Date: 2026-05-21

表结构与索引以各 ORM 模型的 __tablename__ / __table_args__ 为准；
通过 ``Base.metadata.create_all`` 建表（逻辑外键，无数据库 FK）。

历史说明：原 002–012 增量迁移曾合并进 001；``002_agt_schedules`` 为后续补表。
新环境：``alembic upgrade head``。已跑过 001 的库需再执行至 002 以创建 ``agt_schedules`` 等增量表。

"""

from typing import Sequence, Union

from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.infra.db import Base
    from app.models.registry import load_all_models

    load_all_models()
    bind = op.get_bind()
    Base.metadata.create_all(bind)


def downgrade() -> None:
    from app.infra.db import Base
    from app.models.registry import load_all_models

    load_all_models()
    bind = op.get_bind()
    Base.metadata.drop_all(bind)
