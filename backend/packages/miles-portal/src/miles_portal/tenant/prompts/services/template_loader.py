"""画布 PromptTemplate 节点模板库 live 引用加载器（L1 装配）。

``build_prompt_template_loader`` 构造 ``RunContext.resolve_prompt_template`` 回调：
按 ``prompt_template_id`` + ``tenant_id`` 加载启用中模板的 content（live 引用非快照），
供 flow_runtime PromptTemplate 节点使用。原实现迁自 flow_runtime/nodes/rag_nodes.py；
装配点为 chat_rag.flow_run_context 与 flows flow debug-run。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.infra.db import AsyncSessionLocal
from miles_core.soft_delete import is_marked_deleted
from miles_portal.tenant.prompts.models import PromptTemplate


async def _load_prompt_template(
    db: AsyncSession,
    template_id: UUID,
    tenant_id: UUID,
) -> str | None:
    """加载启用中模板 content；非本租户/未启用/已删返回 None。"""
    tpl = await db.get(PromptTemplate, template_id)
    if tpl and tpl.tenant_id == tenant_id and tpl.is_active and not is_marked_deleted(tpl):
        return tpl.content
    return None


def build_prompt_template_loader() -> Callable[[str, str], Awaitable[str | None]]:
    """构造 RunContext.resolve_prompt_template 回调（内部短会话加载）。"""

    async def _loader(prompt_template_id: str, tenant_id: str) -> str | None:
        try:
            tid = UUID(str(prompt_template_id))
            tenant_uuid = UUID(tenant_id)
        except (ValueError, TypeError):
            return None
        async with AsyncSessionLocal() as db:
            return await _load_prompt_template(db, tid, tenant_uuid)

    return _loader
