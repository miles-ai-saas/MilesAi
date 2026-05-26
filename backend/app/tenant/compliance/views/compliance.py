"""合规 HTTP API：词库、词条、扫描绑定、拦截日志与试跑。"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db import get_db
from app.core.deps import get_page_params, require_permissions
from app.common.response import ok, page_ok
from app.core.tenant import TenantContext
from app.common.schema import ApiResponse, PageParams, PageResult
from app.tenant.compliance.schemas.meta import ComplianceMetaOut
from app.tenant.compliance.schemas.compliance import (
    ComplianceScanBindingsOut,
    ComplianceScanBindingsUpdate,
    ComplianceScanRequest,
    ComplianceScanResult,
    EntryLibrariesUpdate,
    InterceptLogOut,
    LibraryWordBatchCreate,
    LibraryWordCreate,
    LibraryWordOut,
    LibraryWordUpdate,
    SensitiveWordEntryOut,
    WordLibraryCreate,
    WordLibraryOut,
    WordLibraryUpdate,
)
from app.tenant.compliance.services.compliance import ComplianceService

router = APIRouter()


def _svc(db: AsyncSession, ctx: TenantContext) -> ComplianceService:
    return ComplianceService(db, ctx)


# GET */meta：枚举展示字典，须在 /{id} 等路径参数路由之前注册
@router.get("/meta", response_model=ApiResponse[ComplianceMetaOut])
async def compliance_meta(
    ctx: TenantContext = Depends(require_permissions("compliance:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).get_meta())


# --- 扫描绑定 ---


@router.get("/bindings", response_model=ApiResponse[ComplianceScanBindingsOut])
async def get_scan_bindings(
    ctx: TenantContext = Depends(require_permissions("compliance:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).get_scan_bindings())


@router.put("/bindings", response_model=ApiResponse[ComplianceScanBindingsOut])
async def set_scan_bindings(
    body: ComplianceScanBindingsUpdate,
    ctx: TenantContext = Depends(require_permissions("compliance:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).set_scan_bindings(body))


# --- 词库 ---


@router.get("/libraries", response_model=ApiResponse[PageResult[WordLibraryOut]])
async def list_libraries(
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("compliance:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await _svc(db, ctx).list_libraries(params)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("/libraries", response_model=ApiResponse[WordLibraryOut])
async def create_library(
    body: WordLibraryCreate,
    ctx: TenantContext = Depends(require_permissions("compliance:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).create_library(body))


@router.get("/libraries/{library_id}", response_model=ApiResponse[WordLibraryOut])
async def get_library(
    library_id: UUID,
    ctx: TenantContext = Depends(require_permissions("compliance:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).get_library(library_id))


@router.patch("/libraries/{library_id}", response_model=ApiResponse[WordLibraryOut])
async def update_library(
    library_id: UUID,
    body: WordLibraryUpdate,
    ctx: TenantContext = Depends(require_permissions("compliance:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).update_library(library_id, body))


@router.delete("/libraries/{library_id}", response_model=ApiResponse[None])
async def delete_library(
    library_id: UUID,
    ctx: TenantContext = Depends(require_permissions("compliance:write")),
    db: AsyncSession = Depends(get_db),
):
    await _svc(db, ctx).delete_library(library_id)
    return ok(message="已删除")


# --- 库内词条 ---


@router.get(
    "/libraries/{library_id}/words",
    response_model=ApiResponse[PageResult[LibraryWordOut]],
)
async def list_library_words(
    library_id: UUID,
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("compliance:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await _svc(db, ctx).list_library_words(library_id, params)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post(
    "/libraries/{library_id}/words",
    response_model=ApiResponse[LibraryWordOut],
)
async def add_library_word(
    library_id: UUID,
    body: LibraryWordCreate,
    ctx: TenantContext = Depends(require_permissions("compliance:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).add_library_word(library_id, body))


@router.post(
    "/libraries/{library_id}/words/batch",
    response_model=ApiResponse[list[LibraryWordOut]],
)
async def batch_add_library_words(
    library_id: UUID,
    body: LibraryWordBatchCreate,
    ctx: TenantContext = Depends(require_permissions("compliance:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).batch_add_library_words(library_id, body))


@router.patch(
    "/libraries/{library_id}/words/{binding_id}",
    response_model=ApiResponse[LibraryWordOut],
)
async def update_library_word(
    library_id: UUID,
    binding_id: UUID,
    body: LibraryWordUpdate,
    ctx: TenantContext = Depends(require_permissions("compliance:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).update_library_word(library_id, binding_id, body))


@router.delete(
    "/libraries/{library_id}/words/{binding_id}",
    response_model=ApiResponse[None],
)
async def delete_library_word(
    library_id: UUID,
    binding_id: UUID,
    ctx: TenantContext = Depends(require_permissions("compliance:write")),
    db: AsyncSession = Depends(get_db),
):
    await _svc(db, ctx).delete_library_word(library_id, binding_id)
    return ok(message="已删除")


# --- 词条 ---


@router.get("/entries/{entry_id}", response_model=ApiResponse[SensitiveWordEntryOut])
async def get_entry(
    entry_id: UUID,
    ctx: TenantContext = Depends(require_permissions("compliance:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).get_entry(entry_id))


@router.put("/entries/{entry_id}/libraries", response_model=ApiResponse[SensitiveWordEntryOut])
async def set_entry_libraries(
    entry_id: UUID,
    body: EntryLibrariesUpdate,
    ctx: TenantContext = Depends(require_permissions("compliance:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).set_entry_libraries(entry_id, body))


# --- 扫描 / 日志 ---


@router.post("/scan", response_model=ApiResponse[ComplianceScanResult])
async def scan_text(
    body: ComplianceScanRequest,
    ctx: TenantContext = Depends(require_permissions("compliance:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc(db, ctx).scan_text(body))


@router.get("/logs", response_model=ApiResponse[PageResult[InterceptLogOut]])
async def list_logs(
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("compliance:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await _svc(db, ctx).list_logs(params)
    return page_ok(result.items, result.total, result.page, result.size)
