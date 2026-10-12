"""Agent 评测 HTTP API。"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.response import ok, page_ok
from miles_common.schema import ApiResponse, PageParams, PageResult
from miles_core.deps import get_page_params, require_permissions
from miles_core.infra.db import get_db
from miles_core.tenant import TenantContext
from miles_portal.tenant.eval.schemas.eval import (
    EvalCaseCreate,
    EvalCaseCsvImport,
    EvalCaseImportResult,
    EvalCaseOut,
    EvalCasePromoteFromCallCreate,
    EvalCaseUpdate,
    EvalDatasetCreate,
    EvalDatasetOut,
    EvalDatasetUpdate,
    EvalRunCreate,
    EvalRunItemOut,
    EvalRunOut,
)
from miles_portal.tenant.eval.services.eval_service import EvalService

router = APIRouter()


@router.get("/datasets", response_model=ApiResponse[PageResult[EvalDatasetOut]])
async def list_datasets(
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await EvalService(db, ctx).list_datasets(params)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("/datasets", response_model=ApiResponse[EvalDatasetOut])
async def create_dataset(
    body: EvalDatasetCreate,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await EvalService(db, ctx).create_dataset(body))


@router.get("/datasets/{dataset_id}", response_model=ApiResponse[EvalDatasetOut])
async def get_dataset(
    dataset_id: UUID,
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await EvalService(db, ctx).get_dataset(dataset_id))


@router.patch("/datasets/{dataset_id}", response_model=ApiResponse[EvalDatasetOut])
async def update_dataset(
    dataset_id: UUID,
    body: EvalDatasetUpdate,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await EvalService(db, ctx).update_dataset(dataset_id, body))


@router.delete("/datasets/{dataset_id}", response_model=ApiResponse[None])
async def delete_dataset(
    dataset_id: UUID,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    await EvalService(db, ctx).delete_dataset(dataset_id)
    return ok(message="已删除")


@router.get("/datasets/{dataset_id}/cases", response_model=ApiResponse[PageResult[EvalCaseOut]])
async def list_cases(
    dataset_id: UUID,
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await EvalService(db, ctx).list_cases(dataset_id, params)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("/datasets/{dataset_id}/cases", response_model=ApiResponse[EvalCaseOut])
async def create_case(
    dataset_id: UUID,
    body: EvalCaseCreate,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await EvalService(db, ctx).create_case(dataset_id, body))


@router.post("/datasets/{dataset_id}/cases/from-call-record", response_model=ApiResponse[EvalCaseOut])
async def promote_case_from_call_record(
    dataset_id: UUID,
    body: EvalCasePromoteFromCallCreate,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    """从调用记录升格用例（成功/失败均可；默认 expected.contains=助手答案）。"""
    return ok(await EvalService(db, ctx).promote_case_from_call_record(dataset_id, body))


@router.post("/datasets/{dataset_id}/cases/import-csv", response_model=ApiResponse[EvalCaseImportResult])
async def import_cases_csv(
    dataset_id: UUID,
    body: EvalCaseCsvImport,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    """CSV 批量导入用例（表头含 query；可选 name / expected_mode / expected_value）。"""
    return ok(await EvalService(db, ctx).import_cases_csv(dataset_id, body))


@router.patch("/datasets/{dataset_id}/cases/{case_id}", response_model=ApiResponse[EvalCaseOut])
async def update_case(
    dataset_id: UUID,
    case_id: UUID,
    body: EvalCaseUpdate,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await EvalService(db, ctx).update_case(dataset_id, case_id, body))


@router.delete("/datasets/{dataset_id}/cases/{case_id}", response_model=ApiResponse[None])
async def delete_case(
    dataset_id: UUID,
    case_id: UUID,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    await EvalService(db, ctx).delete_case(dataset_id, case_id)
    return ok(message="已删除")


@router.get("/runs", response_model=ApiResponse[PageResult[EvalRunOut]])
async def list_runs(
    params: PageParams = Depends(get_page_params),
    dataset_id: UUID | None = Query(None),
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await EvalService(db, ctx).list_runs(params, dataset_id=dataset_id)
    return page_ok(result.items, result.total, result.page, result.size)


@router.post("/runs", response_model=ApiResponse[EvalRunOut])
async def create_run(
    body: EvalRunCreate,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await EvalService(db, ctx).create_run(body))


@router.get("/runs/{run_id}", response_model=ApiResponse[EvalRunOut])
async def get_run(
    run_id: UUID,
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await EvalService(db, ctx).get_run(run_id))


@router.post("/runs/{run_id}/start", response_model=ApiResponse[EvalRunOut])
async def start_run(
    run_id: UUID,
    ctx: TenantContext = Depends(require_permissions("agent:write")),
    db: AsyncSession = Depends(get_db),
):
    return ok(await EvalService(db, ctx).start_run(run_id))


@router.get("/runs/{run_id}/items", response_model=ApiResponse[PageResult[EvalRunItemOut]])
async def list_run_items(
    run_id: UUID,
    params: PageParams = Depends(get_page_params),
    ctx: TenantContext = Depends(require_permissions("agent:read")),
    db: AsyncSession = Depends(get_db),
):
    result = await EvalService(db, ctx).list_run_items(run_id, params)
    return page_ok(result.items, result.total, result.page, result.size)
