"""全量初始 schema（合并所有迁移，按当前 ORM 一次性建表）

Revision ID: 001
Revises:
Create Date: 2026-05-21

通过 ``Base.metadata.create_all`` 按当前 ORM 模型全量建表，
等价于原 001–008、ae613709947f–h4i0k8f7g569 共计 18 个增量迁移的效果。

新环境：
    alembic upgrade head

已有库（曾跑过旧版增量链且 schema 已对齐当前 ORM）：
    alembic stamp 001

清库重建：
    drop database 或 drop_all 后 alembic upgrade head
"""

from typing import Sequence, Union

from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from miles_core.infra.db import Base
    from miles_server.registry import load_all_models

    load_all_models()
    bind = op.get_bind()
    Base.metadata.create_all(bind)


def downgrade() -> None:
    from miles_core.infra.db import Base
    from miles_server.registry import load_all_models

    load_all_models()
    bind = op.get_bind()
    Base.metadata.drop_all(bind)
