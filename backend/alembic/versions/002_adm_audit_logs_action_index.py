"""adm_audit_logs 增加 action 索引

Revision ID: 002
Revises: 001
Create Date: 2026-09-14

审计列表支持按 ``action`` 筛选（``AuditLog.action == action``），筛选元数据也用
``SELECT DISTINCT action``；而原索引只有 admin_id / tenant_id / created_at，
两处都要扫 ``adm_audit_logs`` 全表，随日志量线性变慢。

``action`` 只有 32 个硬编码常量（选择度低），但等值筛选与 DISTINCT 都能走
index-only scan，代价可控。

注意索引建在大表上会阻塞写入：生产环境若表已很大，请在事务外改用
``CREATE INDEX CONCURRENTLY`` 手工执行（alembic 默认在事务内跑迁移）。
故此处用 ``IF NOT EXISTS``：新库经 001 的 ``create_all`` 已按 ORM 建出该索引，
重复执行需为 no-op。
"""

from typing import Sequence, Union

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEX = "idx_adm_audit_logs_action"
_TABLE = "adm_audit_logs"


def upgrade() -> None:
    op.execute(f"CREATE INDEX IF NOT EXISTS {_INDEX} ON {_TABLE} (action)")


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {_INDEX}")
