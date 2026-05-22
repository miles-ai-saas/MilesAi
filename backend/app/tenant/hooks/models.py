"""智能体执行流程钩子：切面扩展点，与内容合规（敏感词）分离。"""

import enum
import uuid

from sqlalchemy import Boolean, Index, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infra.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class HookType(str, enum.Enum):
    HTTP = "http"
    PYTHON = "python"


class HookTrigger(str, enum.Enum):
    """挂载时机：调用、推理、工具、错误等关键节点。"""

    BEFORE_CALL = "before_call"
    AFTER_CALL = "after_call"
    BEFORE_REASONING = "before_reasoning"
    AFTER_REASONING = "after_reasoning"
    BEFORE_TOOL = "before_tool"
    AFTER_TOOL = "after_tool"
    ON_ERROR = "on_error"


class HookScope(str, enum.Enum):
    GLOBAL = "global"
    AGENT = "agent"
    FLOW = "flow"
    TOOL = "tool"
    APP = "app"


class HookDefinition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "hook_definitions"
    __table_args__ = (Index("idx_hook_definitions_tenant_id", "tenant_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    hook_type: Mapped[HookType] = mapped_column(
        SAEnum(HookType, name="hook_type", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    bindings: Mapped[list["HookBinding"]] = relationship(
        "HookBinding",
        back_populates="hook",
        foreign_keys="HookBinding.hook_id",
        primaryjoin="HookDefinition.id == HookBinding.hook_id",
    )


class HookBinding(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "hook_bindings"
    __table_args__ = (
        Index("idx_hook_bindings_tenant_id", "tenant_id"),
        Index("idx_hook_bindings_hook_id", "hook_id"),
        Index(
            "un_hook_bindings_hook_scope_target_trigger",
            "hook_id",
            "scope",
            "target_id",
            "trigger",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    hook_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scope: Mapped[HookScope] = mapped_column(
        SAEnum(HookScope, name="hook_scope", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    trigger: Mapped[HookTrigger] = mapped_column(
        SAEnum(HookTrigger, name="hook_trigger", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    hook: Mapped["HookDefinition"] = relationship(
        "HookDefinition",
        back_populates="bindings",
        foreign_keys=[hook_id],
        primaryjoin="HookBinding.hook_id == HookDefinition.id",
    )
