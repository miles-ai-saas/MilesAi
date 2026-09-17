"""流程画布 ORM：Flow 主表 + 版本化 graph_json（FlowVersion）。"""

import enum
import uuid

from sqlalchemy import Enum, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from miles_core.infra.db import Base
from miles_core.models.base import TimestampMixin, UUIDPrimaryKeyMixin


# 流程发布状态：草稿 / 已发布。
class FlowStatus(enum.StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"


class Flow(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """流程画布主表；``current_version`` 指向最新 graph_json 版本。"""

    __tablename__ = "flow_flows"
    __table_args__ = (Index("idx_flow_flows_tenant_id", "tenant_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[FlowStatus] = mapped_column(
        Enum(FlowStatus, name="flow_status", values_callable=lambda x: [e.value for e in x]),
        default=FlowStatus.DRAFT,
        nullable=False,
    )
    current_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    versions: Mapped[list["FlowVersion"]] = relationship(
        "FlowVersion",
        back_populates="flow",
        foreign_keys="FlowVersion.flow_id",
        primaryjoin="Flow.id == FlowVersion.flow_id",
        cascade="all, delete-orphan",
    )


class FlowVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """每次 save_graph 递增 version；LangGraph 编译 graph_json 执行。"""

    __tablename__ = "flow_versions"
    __table_args__ = (
        Index("idx_flow_versions_flow_id", "flow_id"),
        UniqueConstraint("flow_id", "version", name="uk_flow_versions_flow_id_version"),
    )

    flow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    graph_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    editor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)

    flow: Mapped["Flow"] = relationship(
        "Flow",
        back_populates="versions",
        foreign_keys=[flow_id],
        primaryjoin="FlowVersion.flow_id == Flow.id",
    )
