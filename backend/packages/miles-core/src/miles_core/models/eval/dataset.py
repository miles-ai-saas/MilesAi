"""评测数据集与用例 ORM。"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from miles_core.infra.db import Base
from miles_core.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class EvalDataset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """租户级评测数据集。"""

    __tablename__ = "eval_datasets"
    __table_args__ = (Index("idx_eval_datasets_tenant_updated", "tenant_id", "updated_at"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class EvalCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """数据集内单条用例。

    ``expected`` JSONB 约定（可选）：
    - ``exact``: 答案须完全相等
    - ``contains``: 答案须包含该子串
    - ``contains_all``: 答案须包含列表中全部子串
    - ``rubric``: LLM judge 评分说明（需 run 开启 llm_judge）
    """

    __tablename__ = "eval_cases"
    __table_args__ = (Index("idx_eval_cases_dataset_sort", "dataset_id", "sort_index"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("eval_datasets.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    expected: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    sort_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
