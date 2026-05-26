"""RunContext 辅助（附件解析等）。"""

from uuid import UUID

from app.common.exceptions import BadRequestError
from app.common.schemas.media import MediaRefIn
from app.core.tenant import TenantContext
from app.flow_runtime.types import RunContext


def tenant_context_from_run(ctx: RunContext) -> TenantContext:
    """由 RunContext 构造租户上下文，供 AttachmentService / resolve_media_refs。"""
    if not ctx.user_id:
        raise BadRequestError("流程运行缺少 user_id，无法读取附件")
    return TenantContext(
        user_id=UUID(ctx.user_id),
        tenant_id=UUID(ctx.tenant_id),
        username="flow-runtime",
        is_superuser=ctx.is_superuser,
        permissions=ctx.permissions,
    )


def media_refs_from_run(ctx: RunContext) -> list[MediaRefIn]:
    """RunContext.media（dict 列表）→ MediaRefIn。"""
    refs: list[MediaRefIn] = []
    for item in ctx.media or []:
        if isinstance(item, MediaRefIn):
            refs.append(item)
        elif isinstance(item, dict) and item.get("attachment_id"):
            refs.append(MediaRefIn.model_validate(item))
    return refs
