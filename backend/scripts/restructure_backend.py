#!/usr/bin/env python3
"""一次性将 backend 调整为 apps / admin / tenant / common 分层结构。"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"

# (src relative to app/, dst relative to app/)
MOVES: list[tuple[str, str]] = [
    # --- common ---
    ("core/response.py", "common/response.py"),
    ("core/exceptions.py", "common/exceptions.py"),
    ("core/handlers.py", "common/handlers.py"),
    ("schemas/common.py", "common/schema.py"),
    ("core/pagination.py", "common/pagination.py"),
    # --- admin app_sys ---
    ("services/admin_auth_service.py", "admin/app_sys/services/auth.py"),
    ("schemas/admin.py", "admin/app_sys/schemas/auth.py"),  # partial; ops schemas separate
    ("core/admin_deps.py", "admin/app_sys/deps.py"),
    ("core/admin_security.py", "admin/app_sys/security.py"),
    # --- admin app_ops ---
    ("services/admin_tenant_service.py", "admin/app_ops/services/tenant.py"),
    ("services/admin_billing_service.py", "admin/app_ops/services/billing.py"),
    ("services/admin_risk_service.py", "admin/app_ops/services/risk.py"),
    ("services/admin_audit.py", "admin/app_ops/services/audit.py"),
    ("services/admin_seed.py", "admin/seeds/admin_seed.py"),
    ("models/admin_ops.py", "admin/app_ops/models.py"),
    # --- tenant modules ---
    ("api/v1/auth.py", "tenant/auth/views/auth.py"),
    ("services/auth_service.py", "tenant/auth/services/auth.py"),
    ("schemas/auth.py", "tenant/auth/schemas/auth.py"),
    ("api/v1/users.py", "tenant/system/views/users.py"),
    ("api/v1/tenants.py", "tenant/system/views/tenants.py"),
    ("api/v1/health.py", "tenant/system/views/health.py"),
    ("api/v1/models.py", "tenant/system/views/models.py"),
    ("services/user_service.py", "tenant/system/services/user.py"),
    ("services/tenant_service.py", "tenant/system/services/tenant.py"),
    ("services/health_service.py", "tenant/system/services/health.py"),
    ("schemas/user.py", "tenant/system/schemas/user.py"),
    ("schemas/tenant.py", "tenant/system/schemas/tenant.py"),
    ("api/v1/kb.py", "tenant/kb/views/kb.py"),
    ("services/kb_service.py", "tenant/kb/services/kb.py"),
    ("services/ingest_service.py", "tenant/kb/services/ingest.py"),
    ("schemas/kb.py", "tenant/kb/schemas/kb.py"),
    ("api/v1/flows.py", "tenant/flows/views/flows.py"),
    ("services/flow_service.py", "tenant/flows/services/flow.py"),
    ("schemas/flow.py", "tenant/flows/schemas/flow.py"),
    ("api/v1/agents.py", "tenant/agents/views/agents.py"),
    ("services/agent_service.py", "tenant/agents/services/agent.py"),
    ("schemas/agent.py", "tenant/agents/schemas/agent.py"),
    ("api/v1/marketplace.py", "tenant/marketplace/views/marketplace.py"),
    ("services/marketplace_service.py", "tenant/marketplace/services/marketplace.py"),
    ("services/marketplace_seed.py", "tenant/seeds/marketplace_seed.py"),
    ("schemas/marketplace.py", "tenant/marketplace/schemas/marketplace.py"),
    ("models/marketplace.py", "tenant/marketplace/models.py"),
    ("api/v1/compliance.py", "tenant/compliance/views/compliance.py"),
    ("services/compliance_service.py", "tenant/compliance/services/compliance.py"),
    ("services/compliance_pipeline.py", "tenant/compliance/services/pipeline.py"),
    ("services/hook_executor.py", "tenant/compliance/services/hook_executor.py"),
    ("schemas/compliance.py", "tenant/compliance/schemas/compliance.py"),
    ("models/compliance.py", "tenant/compliance/models.py"),
    ("api/v1/tools.py", "tenant/tools/views/tools.py"),
    ("services/tools_service.py", "tenant/tools/services/tools.py"),
    ("schemas/tools.py", "tenant/tools/schemas/tools.py"),
    ("models/tools.py", "tenant/tools/models.py"),
    ("api/v1/monitor.py", "tenant/monitor/views/monitor.py"),
    ("services/monitor_service.py", "tenant/monitor/services/monitor.py"),
    ("schemas/monitor.py", "tenant/monitor/schemas/monitor.py"),
    ("api/v1/tasks.py", "tenant/tasks/views/tasks.py"),
    ("services/task_service.py", "tenant/tasks/services/task.py"),
    ("services/task_sync.py", "tenant/tasks/services/sync.py"),
    ("schemas/task.py", "tenant/tasks/schemas/task.py"),
    ("services/seed.py", "tenant/seeds/seed.py"),
    ("services/migrate.py", "apps/migrate.py"),
    ("services/base.py", "core/service.py"),
    # workers
    ("celery_app/app.py", "workers/app.py"),
    ("celery_app/tasks/ingest.py", "workers/tasks/ingest.py"),
    ("celery_app/tasks/health.py", "workers/tasks/health.py"),
    ("celery_app/tasks/__init__.py", "workers/tasks/__init__.py"),
]

IMPORT_REPLACEMENTS = [
    (r"\bfrom app\.core\.response\b", "from app.common.response"),
    (r"\bfrom app\.core\.exceptions\b", "from app.common.exceptions"),
    (r"\bfrom app\.core\.handlers\b", "from app.common.handlers"),
    (r"\bfrom app\.schemas\.common\b", "from app.common.schema"),
    (r"\bfrom app\.core\.pagination\b", "from app.common.pagination"),
    (r"\bfrom app\.core\.admin_deps\b", "from app.admin.app_sys.deps"),
    (r"\bfrom app\.core\.admin_security\b", "from app.admin.app_sys.security"),
    (r"\bfrom app\.services\.admin_auth_service\b", "from app.admin.app_sys.services.auth"),
    (r"\bfrom app\.services\.admin_tenant_service\b", "from app.admin.app_ops.services.tenant"),
    (r"\bfrom app\.services\.admin_billing_service\b", "from app.admin.app_ops.services.billing"),
    (r"\bfrom app\.services\.admin_risk_service\b", "from app.admin.app_ops.services.risk"),
    (r"\bfrom app\.services\.admin_audit\b", "from app.admin.app_ops.services.audit"),
    (r"\bfrom app\.services\.admin_seed\b", "from app.admin.seeds.admin_seed"),
    (r"\bfrom app\.schemas\.admin\b", "from app.admin.app_sys.schemas.auth"),
    (r"\bfrom app\.models\.admin_ops\b", "from app.admin.app_ops.models"),
    (r"\bfrom app\.services\.auth_service\b", "from app.tenant.auth.services.auth"),
    (r"\bfrom app\.schemas\.auth\b", "from app.tenant.auth.schemas.auth"),
    (r"\bfrom app\.services\.user_service\b", "from app.tenant.system.services.user"),
    (r"\bfrom app\.services\.tenant_service\b", "from app.tenant.system.services.tenant"),
    (r"\bfrom app\.services\.health_service\b", "from app.tenant.system.services.health"),
    (r"\bfrom app\.schemas\.user\b", "from app.tenant.system.schemas.user"),
    (r"\bfrom app\.schemas\.tenant\b", "from app.tenant.system.schemas.tenant"),
    (r"\bfrom app\.services\.kb_service\b", "from app.tenant.kb.services.kb"),
    (r"\bfrom app\.services\.ingest_service\b", "from app.tenant.kb.services.ingest"),
    (r"\bfrom app\.schemas\.kb\b", "from app.tenant.kb.schemas.kb"),
    (r"\bfrom app\.services\.flow_service\b", "from app.tenant.flows.services.flow"),
    (r"\bfrom app\.schemas\.flow\b", "from app.tenant.flows.schemas.flow"),
    (r"\bfrom app\.services\.agent_service\b", "from app.tenant.agents.services.agent"),
    (r"\bfrom app\.schemas\.agent\b", "from app.tenant.agents.schemas.agent"),
    (r"\bfrom app\.services\.marketplace_service\b", "from app.tenant.marketplace.services.marketplace"),
    (r"\bfrom app\.services\.marketplace_seed\b", "from app.tenant.seeds.marketplace_seed"),
    (r"\bfrom app\.schemas\.marketplace\b", "from app.tenant.marketplace.schemas.marketplace"),
    (r"\bfrom app\.models\.marketplace\b", "from app.tenant.marketplace.models"),
    (r"\bfrom app\.services\.compliance_service\b", "from app.tenant.compliance.services.compliance"),
    (r"\bfrom app\.services\.compliance_pipeline\b", "from app.tenant.compliance.services.pipeline"),
    (r"\bfrom app\.services\.hook_executor\b", "from app.tenant.compliance.services.hook_executor"),
    (r"\bfrom app\.schemas\.compliance\b", "from app.tenant.compliance.schemas.compliance"),
    (r"\bfrom app\.models\.compliance\b", "from app.tenant.compliance.models"),
    (r"\bfrom app\.services\.tools_service\b", "from app.tenant.tools.services.tools"),
    (r"\bfrom app\.schemas\.tools\b", "from app.tenant.tools.schemas.tools"),
    (r"\bfrom app\.models\.tools\b", "from app.tenant.tools.models"),
    (r"\bfrom app\.services\.monitor_service\b", "from app.tenant.monitor.services.monitor"),
    (r"\bfrom app\.schemas\.monitor\b", "from app.tenant.monitor.schemas.monitor"),
    (r"\bfrom app\.services\.task_service\b", "from app.tenant.tasks.services.task"),
    (r"\bfrom app\.services\.task_sync\b", "from app.tenant.tasks.services.sync"),
    (r"\bfrom app\.schemas\.task\b", "from app.tenant.tasks.schemas.task"),
    (r"\bfrom app\.services\.seed\b", "from app.tenant.seeds.seed"),
    (r"\bfrom app\.services\.migrate\b", "from app.apps.migrate"),
    (r"\bfrom app\.services\.base\b", "from app.core.service"),
    (r"\bfrom app\.celery_app\.app\b", "from app.workers.app"),
    (r"\bfrom app\.celery_app\.tasks", "from app.workers.tasks"),
    (r"\bimport app\.celery_app\.tasks", "import app.workers.tasks"),
    (r"app\.celery_app\.tasks\.ingest", "app.workers.tasks.ingest"),
]


def ensure_init_dirs():
    for dst, _ in MOVES:
        d = (APP / dst).parent
        d.mkdir(parents=True, exist_ok=True)
        while d != APP and d != ROOT:
            init = d / "__init__.py"
            if not init.exists():
                init.write_text('"""Auto package."""\n', encoding="utf-8")
            d = d.parent


def do_moves():
    for src, dst in MOVES:
        sp = APP / src
        dp = APP / dst
        if not sp.exists():
            print(f"SKIP missing: {src}")
            continue
        dp.parent.mkdir(parents=True, exist_ok=True)
        if dp.exists():
            dp.unlink()
        shutil.copy2(sp, dp)
        print(f"MOVE {src} -> {dst}")


def patch_file(path: Path):
    text = path.read_text(encoding="utf-8")
    orig = text
    for pattern, repl in IMPORT_REPLACEMENTS:
        text = re.sub(pattern, repl, text)
    if text != orig:
        path.write_text(text, encoding="utf-8")


def patch_tree():
    for py in ROOT.rglob("*.py"):
        if ".venv" in py.parts or "milesai.egg-info" in py.parts:
            continue
        patch_file(py)


def remove_old():
    old_dirs = [
        APP / "api",
        APP / "services",
        APP / "schemas",
        APP / "celery_app",
    ]
    for d in old_dirs:
        if d.exists():
            shutil.rmtree(d)
            print(f"REMOVED {d.relative_to(ROOT)}")


def main():
    ensure_init_dirs()
    do_moves()
    patch_tree()
    remove_old()
    print("Done. Wire apps/application.py and routers manually if not generated.")


if __name__ == "__main__":
    main()
