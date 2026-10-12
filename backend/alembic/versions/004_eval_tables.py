"""新增 Agent 评测表（eval_datasets / cases / runs / run_items）

Revision ID: 004
Revises: 003
Create Date: 2026-10-12

新库经 001 ``create_all`` 已含本批表时，本迁移为 no-op（按表名过滤 create_all）。
"""

from typing import Sequence, Union

from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = (
    "eval_datasets",
    "eval_cases",
    "eval_runs",
    "eval_run_items",
)


def upgrade() -> None:
    from miles_core.infra.db import Base
    from miles_server.registry import load_all_models

    load_all_models()
    bind = op.get_bind()
    tables = [Base.metadata.tables[name] for name in _TABLES if name in Base.metadata.tables]
    if tables:
        Base.metadata.create_all(bind, tables=tables)


def downgrade() -> None:
    for name in reversed(_TABLES):
        op.execute(f'DROP TABLE IF EXISTS "{name}" CASCADE')
