"""媒体资产 HTTP API：生成物列表、编辑与升格知识库。"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ok, page_ok
from app.common.schema import ApiResponse, PageParams, PageResult
from app.core.deps import get_page_params, require_permissions
from app.core.tenant import TenantContext
from app.infra.db import get_db
from app.tenant.media_assets.schemas.media_asset import (
    MediaAssetOut,
    MediaAssetUpdate,
    PromoteToKbRequest,
)
from app.tenant.media_assets.services.media_asset import MediaAssetService

router = APIRouter()


def _svc(db: AsyncSession, ctx: TenantContext) -> MediaAssetService:
    return MediaAssetService(db, ctx)


@router.get("", response_model=ApiResponse[PageResult[MediaAssetOut]])
async def list_media_assets(
    params: PageParams = Depends(get_page_params),
    kind: str | None = None,
    source: str | None = None,
    has_kb_document: bool | None = None,
    ctx: TenantContext = Depends(require_permissions("attachment:read")),
    db: AsyncSession = Depends(get_db),
):
    """分页列出 AI 生成图片/视频等素材。"""
    result = await _svc(db, ctx).list_assets(params, kind=kind, source=source, has_kb_document=has_kb_document)
    return page_ok(result.items, result.total, result.page, result.size)


@router.get("/{asset_id}", response_model=ApiResponse[MediaAssetOut])
async def get_media_asset(
    asset_id: UUID,
    ctx: TenantContext = Depends(require_permissions("attachment:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).get(asset_id))


@router.patch("/{asset_id}", response_model=ApiResponse[MediaAssetOut])
async def update_media_asset(
    asset_id: UUID,
    body: MediaAssetUpdate,
    ctx: TenantContext = Depends(require_permissions("attachment:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).update(asset_id, body))


@router.delete("/{asset_id}", response_model=ApiResponse[None])
async def delete_media_asset(
    asset_id: UUID,
    ctx: TenantContext = Depends(require_permissions("attachment:write")),
    db: AsyncSession = Depends(get_db),
):
    await _svc(db, ctx).delete(asset_id)
    return ok(message="已删除")


@router.post("/{asset_id}/promote-to-kb", response_model=ApiResponse[MediaAssetOut])
async def promote_media_asset_to_kb(
    asset_id: UUID,
    body: PromoteToKbRequest,
    ctx: TenantContext = Depends(require_permissions("kb:write")),
    db: AsyncSession = Depends(get_db),
):
    """升格为 KB 文档并可选触发 ingest 解析。"""
    return ok(await _svc(db, ctx).promote_to_kb(asset_id, body))
