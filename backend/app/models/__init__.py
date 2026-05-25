"""核心 ORM 聚合导出（Alembic / FastAPI 启动时加载）。

租户域表前缀：kb_*、agt_*、flow_*；系统 sys_*；任务 task_records。
逻辑外键无 DB FK，删除见 app.deletion.cascade。
"""

from app.models.category import CategoryDomain, SysCategory
from app.models.agent import Agent, AgentStatus, AgentSubAgentBinding, agent_kb_bindings
from app.tenant.compliance.models import InterceptLog, SensitiveAction, SensitiveWord
from app.tenant.hooks.models import (
    HookBinding,
    HookDefinition,
    HookScope,
    HookTrigger,
    HookType,
)
from app.tenant.mcp.models import McpService, McpStatus
from app.tenant.prompts.models import PromptTemplate
from app.tenant.skills.models import SkillPackage
from app.models.flow import Flow, FlowStatus, FlowVersion
from app.models.attachment import Attachment
from app.models.kb import Document, DocumentChunk, DocumentStatus, KnowledgeBase, VectorRef
from app.models.kb_search_log import KbSearchLog
from app.tenant.marketplace.models import (
    AppCategory,
    AppInstall,
    AppRating,
    MarketplaceApp,
    MarketplaceAppStatus,
)
from app.models.model import ModelConfig
from app.models.model_tenant_credential import ModelTenantCredential
from app.models.permission import Permission
from app.models.role import Role, role_permissions, user_roles
from app.models.system import SystemConfig
from app.models.task import CeleryTaskRecord, TaskStatus
from app.tenant.tools.models import Tool, ToolInvocationLog, ToolType
from app.models.tenant import Tenant
from app.models.user import User

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
    "Agent",
    "AgentStatus",
    "AgentSubAgentBinding",
    "ModelConfig",
    "ModelTenantCredential",
    "agent_kb_bindings",
    "Flow",
    "FlowStatus",
    "FlowVersion",
    "CeleryTaskRecord",
    "TaskStatus",
    "SensitiveWord",
    "SensitiveAction",
    "HookDefinition",
    "HookBinding",
    "HookType",
    "HookTrigger",
    "HookScope",
    "InterceptLog",
    "PromptTemplate",
    "SkillPackage",
    "Tool",
    "ToolType",
    "ToolInvocationLog",
    "McpService",
    "McpStatus",
    "AppCategory",
    "MarketplaceApp",
    "MarketplaceAppStatus",
    "AppInstall",
    "AppRating",
    "user_roles",
    "role_permissions",
]
