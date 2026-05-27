"""退役 DeepSeek R1/V3 兼容目录项（deepseek-reasoner / deepseek-chat）。"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DESCRIPTION = (
    "已退役；请迁移至 deepseek-v4-flash（对话/思考）或 deepseek-v4-pro（复杂推理）。"
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "agt_model_configs" not in inspector.get_table_names():
        return
    bind.execute(
        sa.text(
            """
            UPDATE agt_model_configs
            SET publish_status = 'deprecated',
                is_active = false,
                is_featured = false,
                description = :desc
            WHERE tenant_id IS NULL
              AND model_code IN ('deepseek-reasoner', 'deepseek-chat')
            """
        ),
        {"desc": _DESCRIPTION},
    )


def downgrade() -> None:
    pass
