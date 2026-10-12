"""``list_attachments`` 内置工具：按资源范围列出附件元数据（只读）。

范围语义
--------
- **禁止**无范围列出整个租户附件（避免 Agent 扫库）。
- **显式范围**：``resource_type`` + ``resource_id`` 成对传入时优先使用。
- **默认范围**：对话/工具执行上下文带 ``agent_id`` 时，默认
  ``resource_type=agent`` + ``resource_id=<agent_id>``（与生图/生视频落库一致）。
- ``purpose`` 为可选附加过滤（如 ``chat`` / ``chat_generated``）。
- 仅返回元数据，不读对象存储内容；单页上限 ``MAX_PAGE_SIZE``。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.exceptions import BadRequestError
from miles_common.schema import PageParams
from miles_core.tenant import TenantContext
from miles_portal.tenant.attachments.services.attachment import AttachmentService

MAX_PAGE_SIZE = 20
DEFAULT_PAGE_SIZE = 10
ALLOWED_PURPOSES = frozenset(
    {"general", "chat", "agent", "flow", "chat_generated", "flow_generated"}
)
ALLOWED_RESOURCE_TYPES = frozenset({"agent", "flow", "session"})


def _parse_uuid(raw: object, *, field: str) -> UUID:
    if not raw:
        raise BadRequestError(f"list_attachments 需要 {field}")
    try:
        return UUID(str(raw))
    except (ValueError, TypeError) as exc:
        raise BadRequestError(f"{field} 非法: {raw}") from exc


def _clamp_page(raw: object, *, default: int = 1) -> int:
    try:
        value = int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return max(1, value)


def _clamp_size(raw: object) -> int:
    try:
        value = int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return DEFAULT_PAGE_SIZE
    return max(1, min(value, MAX_PAGE_SIZE))


def resolve_attachment_list_scope(
    params: dict,
    *,
    agent_id: UUID | None,
) -> tuple[str, UUID, str | None]:
    """解析资源范围；无范围时抛 ``BadRequestError``。

    返回 ``(resource_type, resource_id, purpose)``。
    """
    purpose_raw = params.get("purpose")
    purpose: str | None = None
    if purpose_raw is not None and str(purpose_raw).strip():
        purpose = str(purpose_raw).strip()
        if purpose not in ALLOWED_PURPOSES:
            raise BadRequestError(f"purpose 不支持: {purpose}")

    rt_raw = params.get("resource_type")
    rid_raw = params.get("resource_id")
    has_rt = rt_raw is not None and str(rt_raw).strip()
    has_rid = rid_raw is not None and str(rid_raw).strip()

    if has_rt or has_rid:
        if not (has_rt and has_rid):
            raise BadRequestError("resource_type 与 resource_id 须成对传入")
        resource_type = str(rt_raw).strip()
        if resource_type not in ALLOWED_RESOURCE_TYPES:
            raise BadRequestError(f"resource_type 不支持: {resource_type}")
        return resource_type, _parse_uuid(rid_raw, field="resource_id"), purpose

    if agent_id is not None:
        return "agent", agent_id, purpose

    raise BadRequestError(
        "list_attachments 需要资源范围：传入 resource_type+resource_id，或在智能体对话中调用以默认绑定当前智能体"
    )


async def list_scoped_attachments(
    db: AsyncSession,
    ctx: TenantContext,
    params: dict,
    *,
    agent_id: UUID | None = None,
) -> dict:
    """按解析后的范围分页列出附件元数据。"""
    resource_type, resource_id, purpose = resolve_attachment_list_scope(params, agent_id=agent_id)
    page = _clamp_page(params.get("page"))
    size = _clamp_size(params.get("size"))

    result = await AttachmentService(db, ctx).list_attachments(
        PageParams(page=page, size=size),
        purpose=purpose,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    items = [
        {
            "id": str(a.id),
            "filename": a.filename,
            "mime_type": a.mime_type,
            "file_size": a.file_size,
            "purpose": a.purpose,
            "resource_type": a.resource_type,
            "resource_id": str(a.resource_id) if a.resource_id else None,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in result.items
    ]
    return {
        "items": items,
        "total": result.total,
        "page": result.page,
        "size": result.size,
        "scope": {
            "resource_type": resource_type,
            "resource_id": str(resource_id),
            "purpose": purpose,
        },
    }
