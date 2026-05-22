import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infra.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class A2aPeerStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    ERROR = "error"
    INACTIVE = "inactive"


class A2aPeer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """外部 A2A Agent 登记（Agent Card 缓存）。"""

    __tablename__ = "agt_a2a_peers"
    __table_args__ = (
        Index("idx_agt_a2a_peers_tenant_id", "tenant_id"),
        Index("un_agt_a2a_peers_tenant_name", "tenant_id", "name", unique=True),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    agent_card_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    agent_card_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    auth_config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    card_display_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[A2aPeerStatus] = mapped_column(
        SAEnum(A2aPeerStatus, name="a2a_peer_status", values_callable=lambda x: [e.value for e in x]),
        default=A2aPeerStatus.PENDING,
        nullable=False,
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    bindings: Mapped[list["A2aPeerBinding"]] = relationship(
        "A2aPeerBinding",
        back_populates="peer",
        cascade="all, delete-orphan",
    )
    agent_refs: Mapped[list["AgentA2aPeerRef"]] = relationship(
        "AgentA2aPeerRef",
        back_populates="peer",
        cascade="all, delete-orphan",
    )


class AgentA2aPeerRef(Base):
    """自定义智能体引用外部 A2A Peer（非子智能体）。"""

    __tablename__ = "agt_agent_a2a_peer_refs"
    __table_args__ = (
        Index("idx_agt_agent_a2a_peer_refs_agent", "agent_id"),
        Index("idx_agt_agent_a2a_peer_refs_peer", "peer_id"),
    )

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agt_agents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    peer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agt_a2a_peers.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role_hint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trigger_keywords: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    peer: Mapped["A2aPeer"] = relationship("A2aPeer", back_populates="agent_refs")


class A2aPeerBinding(Base):
    """A2A 宿主智能体 ↔ 外部 peer（P2 创建宿主时使用）。"""

    __tablename__ = "agt_a2a_peer_bindings"
    __table_args__ = (
        Index("idx_agt_a2a_peer_bindings_parent", "parent_agent_id"),
        Index("idx_agt_a2a_peer_bindings_peer", "peer_id"),
    )

    parent_agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agt_agents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    peer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agt_a2a_peers.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role_hint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trigger_keywords: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    peer: Mapped["A2aPeer"] = relationship("A2aPeer", back_populates="bindings")
