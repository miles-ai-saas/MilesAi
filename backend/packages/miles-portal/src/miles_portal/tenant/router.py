"""租户工作台 API 路由汇总（L0）；业务逻辑在各自 services，RAG 调 miles_ai.rag。"""

from fastapi import APIRouter

from miles_portal.tenant.a2a.views import peers as a2a_peers
from miles_portal.tenant.agents.views import agents
from miles_portal.tenant.attachments.views import attachment
from miles_portal.tenant.audit_log.views import audit_log
from miles_portal.tenant.auth.views import auth
from miles_portal.tenant.categories.views import categories
from miles_portal.tenant.compliance.views import compliance
from miles_portal.tenant.flows.views import flows
from miles_portal.tenant.generative.views import jobs as generative_jobs
from miles_portal.tenant.hooks.views import hooks
from miles_portal.tenant.kb.views import kb
from miles_portal.tenant.marketplace.views import marketplace
from miles_portal.tenant.mcp.views import mcp
from miles_portal.tenant.media_assets.views import media_asset
from miles_portal.tenant.models.views import models as model_views
from miles_portal.tenant.monitor.views import monitor
from miles_portal.tenant.prompts.views import prompts
from miles_portal.tenant.skills.views import skills
from miles_portal.tenant.system.views import (
    configs,
    health,
    infra,
    quota,
    roles,
    tenant_storage,
    tenants,
    users,
)
from miles_portal.tenant.tags.views import tags
from miles_portal.tenant.tasks.views import tasks
from miles_portal.tenant.tools.views import tools
from miles_portal.tenant.workbench.views import overview as workbench_overview

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(tenants.router, prefix="/tenants", tags=["tenants"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(roles.router, prefix="/roles", tags=["roles"])
api_router.include_router(configs.router, prefix="/system/configs", tags=["system-config"])
api_router.include_router(infra.router, prefix="/system/infra", tags=["system-infra"])
api_router.include_router(
    tenant_storage.router,
    prefix="/system/object-storage",
    tags=["system-object-storage"],
)
api_router.include_router(quota.router, prefix="/system/quota", tags=["system-quota"])

# 13 项产品能力（按配置 → 编排 → 运行 → 分发）
api_router.include_router(categories.router, prefix="/categories", tags=["categories"])
api_router.include_router(tags.router, prefix="/tags", tags=["tags"])
api_router.include_router(compliance.router, prefix="/compliance", tags=["compliance"])
api_router.include_router(prompts.router, prefix="/prompt-templates", tags=["prompt-templates"])
api_router.include_router(model_views.router, prefix="/models", tags=["models"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(a2a_peers.router, prefix="/a2a/peers", tags=["a2a-peers"])
api_router.include_router(hooks.router, prefix="/hooks", tags=["hooks"])
api_router.include_router(tools.router, prefix="/tools", tags=["tools"])
api_router.include_router(skills.router, prefix="/skill-packages", tags=["skill-packages"])
api_router.include_router(mcp.router, prefix="/mcp", tags=["mcp"])
api_router.include_router(kb.router, prefix="/kb", tags=["knowledge-base"])
api_router.include_router(attachment.router, prefix="/attachments", tags=["attachments"])
api_router.include_router(media_asset.router, prefix="/media-assets", tags=["media-assets"])
api_router.include_router(generative_jobs.router, prefix="/generative/jobs", tags=["generative-jobs"])
api_router.include_router(flows.router, prefix="/flows", tags=["flows"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(monitor.router, prefix="/monitor", tags=["monitor"])
api_router.include_router(marketplace.router, prefix="/marketplace", tags=["marketplace"])
api_router.include_router(audit_log.router, prefix="/audit", tags=["audit"])
api_router.include_router(workbench_overview.router, prefix="/workbench", tags=["workbench"])
