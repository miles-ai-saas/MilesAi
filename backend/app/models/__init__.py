"""核心 ORM 聚合导出（Alembic / FastAPI 启动时加载）。

租户域表（``tenant/*/models``）不在此 re-export，避免循环引用；
统一由 ``app.models.registry.load_all_models`` 按序导入。

域目录：platform / kb / flow / model / media / meta / task / storage / agent / marketplace。
"""

from app.models.agent import (
    Agent,
    AgentChatCall,
    AgentChatMessage,
    AgentChatSession,
    AgentSchedule,
    AgentScheduleRun,
    AgentStatus,
    AgentSubAgentBinding,
    agent_kb_bindings,
)
from app.models.flow import Flow, FlowStatus, FlowVersion
from app.models.kb import Document, DocumentChunk, DocumentStatus, KnowledgeBase, KbSearchLog, VectorRef
from app.models.marketplace import (
    AppCategory,
    AppInstall,
    AppInstallSnapshot,
    AppRating,
    MarketplaceApp,
    MarketplaceAppStatus,
    MarketplaceAppVisibility,
)
from app.models.media import Attachment, MediaAsset
from app.models.meta import CategoryDomain, SysCategory
from app.models.model import (
    GenerativeJob,
    GenerativeJobStatus,
    ModelConfig,
    ModelTenantCredential,
    ModelUsageLog,
)
from app.models.platform import Permission, Role, SystemConfig, Tenant, User, role_permissions, user_roles
from app.models.task import CeleryTaskRecord, TaskStatus

__all__ = [
    "CategoryDomain",
    "SysCategory",
    "Tenant",
    "User",
    "Role",
    "Permission",
    "SystemConfig",
    "KnowledgeBase",
    "Document",
    "DocumentChunk",
    "DocumentStatus",
    "VectorRef",
    "KbSearchLog",
    "Attachment",
    "MediaAsset",
    "AppCategory",
    "AppInstall",
    "AppInstallSnapshot",
    "AppRating",
    "MarketplaceApp",
    "MarketplaceAppStatus",
    "MarketplaceAppVisibility",
    "Agent",
    "AgentStatus",
    "AgentSubAgentBinding",
    "AgentSchedule",
    "AgentScheduleRun",
    "AgentChatCall",
    "AgentChatSession",
    "AgentChatMessage",
    "ModelConfig",
    "ModelUsageLog",
    "ModelTenantCredential",
    "agent_kb_bindings",
    "Flow",
    "FlowStatus",
    "FlowVersion",
    "CeleryTaskRecord",
    "TaskStatus",
    "GenerativeJob",
    "GenerativeJobStatus",
    "user_roles",
    "role_permissions",
]
