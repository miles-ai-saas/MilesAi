"""知识库 HTTP API：KB/文档 CRUD、上传（异步 ingest）、检索与配额。

请求流：路由 → KnowledgeBaseService → Repository / rag.retrieve / Celery。
上传不阻塞解析：仅 OSS + Document 行 + ingest_document.delay。
"""

from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.infra.db import get_db
from miles_core.deps import get_page_params, require_permissions
from miles_common.response import ok, page_ok
from miles_core.tenant import TenantContext
from miles_common.schema import ApiResponse, PageParams, PageResult
from miles_portal.tenant.kb.schemas.meta import KbMetaOut
from miles_portal.tenant.kb.schemas.kb import (
    DocumentChunkOut,
    DocumentOut,
    KbQuotaOut,
    KbSearchLogOut,
    KnowledgeBaseCreate,
    KnowledgeBaseOut,
    KnowledgeBaseUpdate,
    SearchRequest,
    SearchResponse,
)
from miles_portal.tenant.kb.services.kb import KnowledgeBaseService

router = APIRouter()


def _svc(db: AsyncSession, ctx: TenantContext) -> KnowledgeBaseService:
    """构造带租户上下文的 KB 用例服务。"""
    return KnowledgeBaseService(db, ctx)


# GET */meta：枚举展示字典，须在 /{id} 等路径参数路由之前注册
@router.get("/meta", response_model=ApiResponse[KbMetaOut])
async def kb_meta(
    ctx: TenantContext = Depends(require_permissions("kb:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).get_meta())


@router.get("/quota", response_model=ApiResponse[KbQuotaOut])
async def get_kb_quota(
    ctx: TenantContext = Depends(require_permissions("kb:read")),
    db: AsyncSession = Depends(get_db),
):
    """查询当前租户知识库配额（数量、存储等）。"""
    return ok(await _svc(db, ctx).get_quota())


@router.get("", response_model=ApiResponse[PageResult[KnowledgeBaseOut]])
async def list_kbs(
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("kb:read")),
    db: AsyncSession = Depends(get_db),
):
    """分页列出知识库。"""
    result = await _svc(db, ctx).list_kbs(params)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("", response_model=ApiResponse[KnowledgeBaseOut])
async def create_kb(
    body: KnowledgeBaseCreate,
    ctx: TenantContext = Depends(require_permissions("kb:write")),
    db: AsyncSession = Depends(get_db),
):
    """创建知识库并固化 embedding 维度。"""
    return ok(await _svc(db, ctx).create_kb(body))


@router.get("/{kb_id}", response_model=ApiResponse[KnowledgeBaseOut])
async def get_kb(
    kb_id: UUID,
    ctx: TenantContext = Depends(require_permissions("kb:read")),
    db: AsyncSession = Depends(get_db),
):
    """获取单个知识库详情。"""
    return ok(await _svc(db, ctx).get_kb(kb_id))


@router.patch("/{kb_id}", response_model=ApiResponse[KnowledgeBaseOut])
async def update_kb(
    kb_id: UUID,
    body: KnowledgeBaseUpdate,
    ctx: TenantContext = Depends(require_permissions("kb:write")),
    db: AsyncSession = Depends(get_db),
):
    """更新知识库元数据（不含 embedding 维度变更）。"""
    return ok(await _svc(db, ctx).update_kb(kb_id, body))


@router.delete("/{kb_id}", response_model=ApiResponse[None])
async def delete_kb(
    kb_id: UUID,
    ctx: TenantContext = Depends(require_permissions("kb:write")),
    db: AsyncSession = Depends(get_db),
):
    """软删知识库及其下所有文档与向量。"""
    await _svc(db, ctx).delete_kb(kb_id)
    return ok(message="已删除")


@router.get("/{kb_id}/documents", response_model=ApiResponse[PageResult[DocumentOut]])
async def list_documents(
    kb_id: UUID,
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("kb:read")),
    db: AsyncSession = Depends(get_db),
):
    """分页列出文档；READY 状态附带 chunk_count。"""
    result = await _svc(db, ctx).list_documents(kb_id, params)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("/{kb_id}/documents", response_model=ApiResponse[DocumentOut])
async def upload_document(
    kb_id: UUID,
    file: UploadFile = File(...),
    ctx: TenantContext = Depends(require_permissions("kb:document:upload")),
    db: AsyncSession = Depends(get_db),
):
    """上传文件至 OSS 并投递 Celery ingest，返回 PENDING 文档。"""
    return ok(await _svc(db, ctx).upload_document(kb_id, file))


@router.post("/{kb_id}/documents/batch", response_model=ApiResponse[list[DocumentOut]])
async def upload_documents_batch(
    kb_id: UUID,
    files: list[UploadFile] = File(...),
    ctx: TenantContext = Depends(require_permissions("kb:document:upload")),
    db: AsyncSession = Depends(get_db),
):
    """批量上传（最多 20 个），单文件失败跳过。"""
    return ok(await _svc(db, ctx).upload_documents_batch(kb_id, files))


@router.post("/{kb_id}/documents/{document_id}/retry", response_model=ApiResponse[DocumentOut])
async def retry_document(
    kb_id: UUID,
    document_id: UUID,
    ctx: TenantContext = Depends(require_permissions("kb:write")),
    db: AsyncSession = Depends(get_db),
):
    """对失败或已完成文档重新投递 ingest。"""
    return ok(await _svc(db, ctx).retry_document(kb_id, document_id))


@router.get(
    "/{kb_id}/documents/{document_id}/chunks",
    response_model=ApiResponse[PageResult[DocumentChunkOut]],
)
async def list_document_chunks(
    kb_id: UUID,
    document_id: UUID,
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("kb:read")),
    db: AsyncSession = Depends(get_db),
):
    """分页查看文档分片（按 chunk_index 排序）。"""
    result = await _svc(db, ctx).list_document_chunks(kb_id, document_id, params)
    return page_ok(result.items, result.total, result.page, result.size)


@router.delete("/{kb_id}/documents/{document_id}", response_model=ApiResponse[None])
async def delete_document(
    kb_id: UUID,
    document_id: UUID,
    ctx: TenantContext = Depends(require_permissions("kb:write")),
    db: AsyncSession = Depends(get_db),
):
    """删除文档：清分片/向量、删 OSS、软删行。"""
    await _svc(db, ctx).delete_document(kb_id, document_id)
    return ok(message="已删除")


@router.get("/{kb_id}/search-logs", response_model=ApiResponse[PageResult[KbSearchLogOut]])
async def list_kb_search_logs(
    kb_id: UUID,
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("kb:read")),
    db: AsyncSession = Depends(get_db),
):
    """分页查看知识库检索审计日志。"""
    result = await _svc(db, ctx).list_search_logs(kb_id, params)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("/{kb_id}/search", response_model=ApiResponse[SearchResponse])
async def search_kb(
    kb_id: UUID,
    body: SearchRequest,
    ctx: TenantContext = Depends(require_permissions("kb:read")),
    db: AsyncSession = Depends(get_db),
):
    """检索：query 向量化 → vector/hybrid → 可选 rerank → 回填 PG 分片正文。"""
    return ok(await _svc(db, ctx).search(kb_id, body))
