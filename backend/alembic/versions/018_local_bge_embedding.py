"""kb_bases 本地向量化规格对齐 BAAI/bge-base-zh-v1.5

Revision ID: 018
Revises: 017
Create Date: 2026-05-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE kb_bases SET
                embedding_profile = 'local-bge-zh',
                embedding_backend = 'local',
                embedding_model_name = 'BAAI/bge-base-zh-v1.5',
                embedding_dimension = 768
            WHERE embedding_profile <> 'dashscope-v3'
              AND (
                embedding_profile <> 'local-bge-zh'
                OR embedding_model_name <> 'BAAI/bge-base-zh-v1.5'
                OR embedding_dimension <> 768
              )
            """
        )
    )


def downgrade() -> None:
    pass
