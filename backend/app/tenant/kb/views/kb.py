from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db import get_db
from app.core.deps import get_page_params, require_permissions
from app.common.response import ok, page_ok
from app.core.tenant import TenantContext
from app.common.schema import ApiResponse, PageParams, PageResult
from app.tenant.kb.schemas.kb import (
    DocumentOut,
    KbQuotaOut,
    KbSearchLogOut,
    KnowledgeBaseCreate,
    KnowledgeBaseOut,
    KnowledgeBaseUpdate,
    SearchRequest,
    SearchResponse,
)
from app.tenant.kb.services.kb import KnowledgeBaseService

router = APIRouter()


def _svc(db: AsyncSession, ctx: TenantContext) -> KnowledgeBaseService:
    return KnowledgeBaseService(db, ctx)


@router.get("/quota", response_model=ApiResponse[KbQuotaOut])
async def get_kb_quota(
    ctx: TenantContext = Depends(require_permissions("kb:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).get_quota())


@router.get("", response_model=ApiResponse[PageResult[KnowledgeBaseOut]])
async def list_kbs(
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("kb:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await _svc(db, ctx).list_kbs(params)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("", response_model=ApiResponse[KnowledgeBaseOut])
async def create_kb(
    body: KnowledgeBaseCreate,
    ctx: TenantContext = Depends(require_permissions("kb:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).create_kb(body))


@router.get("/{kb_id}", response_model=ApiResponse[KnowledgeBaseOut])
async def get_kb(
    kb_id: UUID,
    ctx: TenantContext = Depends(require_permissions("kb:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).get_kb(kb_id))


@router.patch("/{kb_id}", response_model=ApiResponse[KnowledgeBaseOut])
async def update_kb(
    kb_id: UUID,
    body: KnowledgeBaseUpdate,
    ctx: TenantContext = Depends(require_permissions("kb:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).update_kb(kb_id, body))


@router.delete("/{kb_id}", response_model=ApiResponse[None])
async def delete_kb(
    kb_id: UUID,
    ctx: TenantContext = Depends(require_permissions("kb:write")),
    db: AsyncSession = Depends(get_db),
):
    await _svc(db, ctx).delete_kb(kb_id)
    return ok(message="已删除")


@router.get("/{kb_id}/documents", response_model=ApiResponse[PageResult[DocumentOut]])
async def list_documents(
    kb_id: UUID,
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("kb:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await _svc(db, ctx).list_documents(kb_id, params)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("/{kb_id}/documents", response_model=ApiResponse[DocumentOut])
async def upload_document(
    kb_id: UUID,
    file: UploadFile = File(...),
    ctx: TenantContext = Depends(require_permissions("kb:document:upload")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).upload_document(kb_id, file))


@router.post("/{kb_id}/documents/{document_id}/retry", response_model=ApiResponse[DocumentOut])
async def retry_document(
    kb_id: UUID,
    document_id: UUID,
    ctx: TenantContext = Depends(require_permissions("kb:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).retry_document(kb_id, document_id))


@router.delete("/{kb_id}/documents/{document_id}", response_model=ApiResponse[None])
async def delete_document(
    kb_id: UUID,
    document_id: UUID,
    ctx: TenantContext = Depends(require_permissions("kb:write")),
    db: AsyncSession = Depends(get_db),
):
    await _svc(db, ctx).delete_document(kb_id, document_id)
    return ok(message="已删除")


@router.get("/{kb_id}/search-logs", response_model=ApiResponse[PageResult[KbSearchLogOut]])
async def list_kb_search_logs(
    kb_id: UUID,
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("kb:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await _svc(db, ctx).list_search_logs(kb_id, params)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("/{kb_id}/search", response_model=ApiResponse[SearchResponse])
async def search_kb(
    kb_id: UUID,
    body: SearchRequest,
    ctx: TenantContext = Depends(require_permissions("kb:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).search(kb_id, body))
