"""生成类 prompt 合规扫描（与对话/流程 query 共用词库绑定）。"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import TenantContext
from app.models.compliance.constants import SCAN_MODULE_GENERATIVE
from app.tenant.compliance.services.compliance import ComplianceService


async def check_generative_prompt(
    db: AsyncSession,
    ctx: TenantContext,
    prompt: str,
) -> str:
    """扫描生成 prompt；拦截时抛业务异常，返回脱敏后文本（通常与输入相同）。"""
    compliance = ComplianceService(db, ctx)
    return await compliance.check_input((prompt or "").strip(), module=SCAN_MODULE_GENERATIVE)
