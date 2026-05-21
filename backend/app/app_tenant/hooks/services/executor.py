"""钩子执行器：按挂载时机调用 HTTP / Python 扩展。"""

import logging
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.app_tenant.hooks.models import HookBinding, HookDefinition, HookScope, HookTrigger, HookType
from app.core.soft_delete import not_deleted

logger = logging.getLogger(__name__)


class HookExecutor:
    def __init__(self, db: AsyncSession, tenant_id: UUID) -> None:
        self.db = db
        self.tenant_id = tenant_id

    async def run(
        self,
        *,
        trigger: HookTrigger,
        scope: HookScope,
        target_id: UUID | None,
        payload: dict,
    ) -> list[dict]:
        bindings = await self._load_bindings(trigger, scope, target_id)
        results: list[dict] = []
        for _binding, hook in bindings:
            if hook.hook_type == HookType.HTTP:
                results.append(await self._run_http(hook, payload))
            else:
                logger.warning("python hook not implemented: %s", hook.name)
                results.append({"hook": hook.name, "status": "skipped", "reason": "python_not_implemented"})
        return results

    async def _load_bindings(
        self,
        trigger: HookTrigger,
        scope: HookScope,
        target_id: UUID | None,
    ) -> list[tuple[HookBinding, HookDefinition]]:
        stmt = (
            select(HookBinding)
            .join(HookDefinition, HookBinding.hook_id == HookDefinition.id)
            .where(
                HookBinding.tenant_id == self.tenant_id,
                HookBinding.is_active.is_(True),
                HookDefinition.is_active.is_(True),
                not_deleted(HookBinding),
                not_deleted(HookDefinition),
                HookBinding.trigger == trigger,
            )
            .options(selectinload(HookBinding.hook))
            .order_by(HookBinding.priority.asc())
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        out: list[tuple[HookBinding, HookDefinition]] = []
        for b in rows:
            if b.scope == HookScope.GLOBAL:
                out.append((b, b.hook))
            elif b.scope == scope and (b.target_id is None or b.target_id == target_id):
                out.append((b, b.hook))
        return out

    async def _run_http(self, hook: HookDefinition, payload: dict) -> dict:
        cfg = hook.config or {}
        url = cfg.get("url")
        if not url:
            return {"hook": hook.name, "status": "error", "reason": "missing url"}
        method = str(cfg.get("method", "POST")).upper()
        headers = cfg.get("headers") or {}
        timeout = float(cfg.get("timeout", 5))
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.request(method, url, json=payload, headers=headers)
            return {
                "hook": hook.name,
                "status": "ok" if resp.is_success else "error",
                "http_status": resp.status_code,
            }
        except Exception as exc:
            logger.exception("hook %s failed", hook.name)
            return {"hook": hook.name, "status": "error", "reason": str(exc)}
