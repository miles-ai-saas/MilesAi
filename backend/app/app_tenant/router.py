from fastapi import APIRouter

from app.app_tenant.a2a.views import peers as a2a_peers
from app.app_tenant.agents.views import agents
from app.app_tenant.audit_log.views import audit_log
from app.app_tenant.auth.views import auth
from app.app_tenant.compliance.views import compliance
from app.app_tenant.flows.views import flows
from app.app_tenant.hooks.views import hooks
from app.app_tenant.kb.views import kb
from app.app_tenant.marketplace.views import marketplace
from app.app_tenant.mcp.views import mcp
from app.app_tenant.models.views import models as model_views
from app.app_tenant.monitor.views import monitor
from app.app_tenant.prompts.views import prompts
from app.app_tenant.skills.views import skills
from app.app_tenant.system.views import configs, health, roles, tenants, users
from app.app_tenant.tasks.views import tasks
from app.app_tenant.tools.views import tools
from app.app_tenant.workbench.views import overview as workbench_overview

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(tenants.router, prefix="/tenants", tags=["tenants"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(roles.router, prefix="/roles", tags=["roles"])
api_router.include_router(configs.router, prefix="/system/configs", tags=["system-config"])

# 13 项产品能力（按配置 → 编排 → 运行 → 分发）
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
api_router.include_router(flows.router, prefix="/flows", tags=["flows"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(monitor.router, prefix="/monitor", tags=["monitor"])
api_router.include_router(marketplace.router, prefix="/marketplace", tags=["marketplace"])
api_router.include_router(audit_log.router, prefix="/audit", tags=["audit"])
api_router.include_router(workbench_overview.router, prefix="/workbench", tags=["workbench"])
