"""市场安装应用 → ``HookScope.APP`` 目标解析。

安装记录 ``mkt_installs`` 把本租户克隆出的 ``agent_id`` / ``flow_id`` 关联到 ``app_id``。
对话 / 流程 run 时据此决定是否外层派发应用级钩子。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.models.marketplace.models import AppInstall


async def resolve_install_app_id(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    agent_id: UUID | None = None,
    flow_id: UUID | None = None,
) -> UUID | None:
    """若资源来自本租户某次市场安装，返回对应 ``app_id``；否则 ``None``。"""
    if agent_id is None and flow_id is None:
        return None
    conds = [AppInstall.tenant_id == tenant_id]
    if agent_id is not None:
        conds.append(AppInstall.agent_id == agent_id)
    else:
        conds.append(AppInstall.flow_id == flow_id)
    return await db.scalar(select(AppInstall.app_id).where(*conds).limit(1))
