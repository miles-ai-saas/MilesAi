import enum
import uuid

from sqlalchemy import Column, Enum, Index, Integer, String, Table, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

agent_kb_bindings = Table(
    "agt_kb_bindings",
    Base.metadata,
    Column("agent_id", UUID(as_uuid=True), primary_key=True),
    Column("kb_id", UUID(as_uuid=True), primary_key=True),
    Index("un_agt_kb_bindings_agent_id_kb_id", "agent_id", "kb_id"),
)


class AgentStatus(str, enum.Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"


class Agent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agt_agents"
    __table_args__ = (
        Index("idx_agt_agents_tenant_id", "tenant_id"),
        Index("idx_agt_agents_model_config_id", "model_config_id"),
        Index("idx_agt_agents_published_flow_id", "published_flow_id"),
        Index("idx_agt_agents_prompt_template_id", "prompt_template_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[AgentStatus] = mapped_column(
        Enum(AgentStatus, name="agent_status", values_callable=lambda x: [e.value for e in x]),
        default=AgentStatus.ENABLED,
        nullable=False,
    )
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_template_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    model_config_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    published_flow_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    model_config: Mapped["ModelConfig | None"] = relationship(
        "ModelConfig",
        foreign_keys=[model_config_id],
        primaryjoin="Agent.model_config_id == ModelConfig.id",
    )
    published_flow: Mapped["Flow | None"] = relationship(
        "Flow",
        foreign_keys=[published_flow_id],
        primaryjoin="Agent.published_flow_id == Flow.id",
    )
    knowledge_bases: Mapped[list["KnowledgeBase"]] = relationship(
        "KnowledgeBase",
        secondary=agent_kb_bindings,
        primaryjoin="Agent.id == agt_kb_bindings.c.agent_id",
        secondaryjoin="KnowledgeBase.id == agt_kb_bindings.c.kb_id",
    )
    sub_agent_bindings: Mapped[list["AgentSubAgentBinding"]] = relationship(
        "AgentSubAgentBinding",
        foreign_keys="AgentSubAgentBinding.parent_agent_id",
        primaryjoin="Agent.id == AgentSubAgentBinding.parent_agent_id",
        cascade="all, delete-orphan",
        order_by="AgentSubAgentBinding.sort_order",
    )


class AgentSubAgentBinding(Base):
    __tablename__ = "agt_sub_agent_bindings"
    __table_args__ = (
        Index("idx_agt_sub_agent_bindings_parent", "parent_agent_id"),
        Index("idx_agt_sub_agent_bindings_child", "child_agent_id"),
    )

    parent_agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    child_agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    role_hint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    child_agent: Mapped["Agent"] = relationship(
        "Agent",
        foreign_keys=[child_agent_id],
        primaryjoin="AgentSubAgentBinding.child_agent_id == Agent.id",
    )
