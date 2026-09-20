"""adm_rate_limit_rules 增加 scope（限流计量维度）

Revision ID: 003
Revises: 002
Create Date: 2026-09-20

按 API Key 限流需要区分「这条规则算哪个维度」：A2A 对外端点要按调用方的 Key 计数，
而平台通用限流仍按来源 IP。默认 ``ip`` 是向后兼容的关键 —— 存量规则语义不变，
无需数据回填。

用 ``VARCHAR`` 而非 PG 原生枚举：本列只有两个取值、校验在应用层做，而枚举类型要
``CREATE TYPE`` 且拖累 ``downgrade``。``IF NOT EXISTS`` 沿用 002 的理由：新库经 001 的
``create_all`` 已按 ORM 建出该列，重复执行需为 no-op。
"""

from typing import Sequence, Union

from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "adm_rate_limit_rules"


def upgrade() -> None:
    op.execute(f"ALTER TABLE {_TABLE} ADD COLUMN IF NOT EXISTS scope VARCHAR(16) NOT NULL DEFAULT 'ip'")


def downgrade() -> None:
    op.execute(f"ALTER TABLE {_TABLE} DROP COLUMN IF EXISTS scope")
