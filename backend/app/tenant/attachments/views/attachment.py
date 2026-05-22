"""会话附件 HTTP API（非 KB 文档，仍计存储配额）。"""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ok, page_ok
from app.common.schema import ApiResponse, PageParams, PageResult
from app.core.deps import get_page_params, require_permissions
from app.core.tenant import TenantContext
from app.infra.db import get_db
from app.tenant.attachments.schemas.attachment import AttachmentOut, AttachmentUploadMeta
from app.tenant.attachments.services.attachment import AttachmentService

router = APIRouter()


def _svc(db: AsyncSession, ctx: TenantContext) -> AttachmentService:
    return AttachmentService(db, ctx)


@router.get("", response_model=ApiResponse[PageResult[AttachmentOut]])
async def list_attachments(
    params: PageParams = Depends(get_page_params),
    purpose: str | None = None,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    ctx: TenantContext = Depends(require_permissions("attachment:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await _svc(db, ctx).list_attachments(
        params,
        purpose=purpose,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("", response_model=ApiResponse[AttachmentOut])
async def upload_attachment(
    file: UploadFile = File(...),
    purpose: str = Form("general"),
    resource_type: str | None = Form(None),
    resource_id: UUID | None = Form(None),
    ctx: TenantContext = Depends(require_permissions("attachment:upload")),
    db: AsyncSession = Depends(get_db),
):
    meta = AttachmentUploadMeta(
        purpose=purpose,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    return ok(await _svc(db, ctx).upload(file, meta))


@router.get("/{attachment_id}", response_model=ApiResponse[AttachmentOut])
async def get_attachment(
    attachment_id: UUID,
    ctx: TenantContext = Depends(require_permissions("attachment:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).get(attachment_id))


@router.delete("/{attachment_id}", response_model=ApiResponse[None])
async def delete_attachment(
    attachment_id: UUID,
    ctx: TenantContext = Depends(require_permissions("attachment:write")),
    db: AsyncSession = Depends(get_db),
):
    await _svc(db, ctx).delete(attachment_id)
    return ok(message="已删除")
