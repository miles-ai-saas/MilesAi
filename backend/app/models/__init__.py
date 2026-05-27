"""核心 ORM 聚合导出（Alembic / FastAPI 启动时加载）。

租户域表（``tenant/*/models``）不在此 re-export，避免
``tenant.models → app.models.base → app.models.__init__`` 循环引用；
统一由 ``app.models.registry.load_all_models`` 按序导入。

表前缀：kb_*、agt_*、flow_*；系统 sys_*；任务 task_records。
逻辑外键无 DB FK，删除见 app.deletion.cascade。
"""

from app.models.category import CategoryDomain, SysCategory
from app.models.agent import Agent, AgentStatus, AgentSubAgentBinding, agent_kb_bindings
from app.models.agent_schedule import AgentSchedule
from app.models.agent_schedule_run import AgentScheduleRun
from app.models.flow import Flow, FlowStatus, FlowVersion
from app.models.attachment import Attachment
from app.models.media_asset import MediaAsset
from app.models.model_usage_log import ModelUsageLog
from app.models.generative_job import GenerativeJob, GenerativeJobStatus
from app.models.kb import Document, DocumentChunk, DocumentStatus, KnowledgeBase, VectorRef
from app.models.kb_search_log import KbSearchLog
from app.models.model import ModelConfig
from app.models.model_tenant_credential import ModelTenantCredential
from app.models.permission import Permission
from app.models.role import Role, role_permissions, user_roles
from app.models.system import SystemConfig
from app.models.task import CeleryTaskRecord, TaskStatus
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
    "MediaAsset",
    "Agent",
    "AgentStatus",
    "AgentSubAgentBinding",
    "AgentSchedule",
    "AgentScheduleRun",
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
