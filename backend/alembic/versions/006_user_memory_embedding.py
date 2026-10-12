"""agt_user_agent_memories 增加 content_embedding（JSONB 向量）

Revision ID: 006
Revises: 005
Create Date: 2026-10-12
"""

from typing import Sequence, Union

from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        'ALTER TABLE agt_user_agent_memories '
        "ADD COLUMN IF NOT EXISTS content_embedding JSONB"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE agt_user_agent_memories DROP COLUMN IF EXISTS content_embedding")
