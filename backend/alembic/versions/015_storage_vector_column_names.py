"""kb 文档与向量引用列改为通用语义（object_bucket/key、vector_id）

Revision ID: 015
Revises: 014
Create Date: 2026-05-22
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _col_exists(table: str, col: str) -> bool:
    bind = op.get_bind()
    return col in {c["name"] for c in inspect(bind).get_columns(table)}


def _index_exists(table: str, name: str) -> bool:
    bind = op.get_bind()
    return name in {i["name"] for i in inspect(bind).get_indexes(table)}


def upgrade() -> None:
    if _col_exists("kb_documents", "minio_bucket"):
        op.alter_column("kb_documents", "minio_bucket", new_column_name="object_bucket")
    if _col_exists("kb_documents", "minio_key"):
        op.alter_column("kb_documents", "minio_key", new_column_name="object_key")

    if _col_exists("kb_vector_refs", "weaviate_uuid"):
        if _index_exists("kb_vector_refs", "idx_kb_vector_refs_weaviate_uuid"):
            op.drop_index("idx_kb_vector_refs_weaviate_uuid", table_name="kb_vector_refs")
        op.alter_column("kb_vector_refs", "weaviate_uuid", new_column_name="vector_id")
    if not _index_exists("kb_vector_refs", "idx_kb_vector_refs_vector_id"):
        op.create_index(
            "idx_kb_vector_refs_vector_id",
            "kb_vector_refs",
            ["vector_id"],
        )


def downgrade() -> None:
    if _col_exists("kb_vector_refs", "vector_id"):
        if _index_exists("kb_vector_refs", "idx_kb_vector_refs_vector_id"):
            op.drop_index("idx_kb_vector_refs_vector_id", table_name="kb_vector_refs")
        op.alter_column("kb_vector_refs", "vector_id", new_column_name="weaviate_uuid")
    if not _index_exists("kb_vector_refs", "idx_kb_vector_refs_weaviate_uuid"):
        op.create_index(
            "idx_kb_vector_refs_weaviate_uuid",
            "kb_vector_refs",
            ["weaviate_uuid"],
        )

    if _col_exists("kb_documents", "object_key"):
        op.alter_column("kb_documents", "object_key", new_column_name="minio_key")
    if _col_exists("kb_documents", "object_bucket"):
        op.alter_column("kb_documents", "object_bucket", new_column_name="minio_bucket")
