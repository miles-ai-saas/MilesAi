"""评测数据集 / 用例 / 运行 CRUD 与启动批跑。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_common.exceptions import BadRequestError, NotFoundError
from miles_common.schema import PageParams, PageResult
from miles_core.jobs.tasks import RUN_EVAL_BATCH
from miles_core.models.agent import Agent
from miles_core.models.eval import EvalCase, EvalDataset, EvalRun, EvalRunItem, EvalRunStatus
from miles_core.service import BaseService
from miles_core.soft_delete import append_not_deleted, is_marked_deleted, mark_deleted
from miles_core.tenant import TenantContext, assert_tenant_access, tenant_filters
from miles_portal.tenant.eval.schemas.eval import (
    EvalCaseCreate,
    EvalCaseOut,
    EvalCaseUpdate,
    EvalDatasetCreate,
    EvalDatasetOut,
    EvalDatasetUpdate,
    EvalRunCreate,
    EvalRunItemOut,
    EvalRunOut,
)
from miles_worker.app import celery_app


class EvalService(BaseService):
    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)

    # --- dataset ---

    async def list_datasets(self, params: PageParams) -> PageResult[EvalDatasetOut]:
        filters = append_not_deleted(tenant_filters(self.ctx, EvalDataset.tenant_id), EvalDataset)
        total = await self.db.scalar(select(func.count()).select_from(EvalDataset).where(*filters))
        rows = (
            await self.db.execute(
                select(EvalDataset)
                .where(*filters)
                .order_by(EvalDataset.updated_at.desc())
                .offset((params.page - 1) * params.size)
                .limit(params.size)
            )
        ).scalars().all()
        counts = await self._case_counts({r.id for r in rows})
        return PageResult(
            items=[self._dataset_out(r, counts.get(r.id, 0)) for r in rows],
            total=total or 0,
            page=params.page,
            size=params.size,
        )

    async def create_dataset(self, body: EvalDatasetCreate) -> EvalDatasetOut:
        row = EvalDataset(
            tenant_id=self.ctx.tenant_id,
            name=body.name.strip(),
            description=body.description,
            created_by=self.ctx.user_id,
        )
        self.db.add(row)
        await self.db.flush()
        return self._dataset_out(row, 0)

    async def get_dataset(self, dataset_id: UUID) -> EvalDatasetOut:
        row = await self._get_dataset(dataset_id)
        counts = await self._case_counts({row.id})
        return self._dataset_out(row, counts.get(row.id, 0))

    async def update_dataset(self, dataset_id: UUID, body: EvalDatasetUpdate) -> EvalDatasetOut:
        row = await self._get_dataset(dataset_id)
        if body.name is not None:
            row.name = body.name.strip()
        if body.description is not None:
            row.description = body.description
        await self.db.flush()
        counts = await self._case_counts({row.id})
        return self._dataset_out(row, counts.get(row.id, 0))

    async def delete_dataset(self, dataset_id: UUID) -> None:
        row = await self._get_dataset(dataset_id)
        mark_deleted(row)
        await self.db.flush()

    # --- case ---

    async def list_cases(self, dataset_id: UUID, params: PageParams) -> PageResult[EvalCaseOut]:
        await self._get_dataset(dataset_id)
        filters = [
            EvalCase.tenant_id == self.ctx.tenant_id,
            EvalCase.dataset_id == dataset_id,
        ]
        total = await self.db.scalar(select(func.count()).select_from(EvalCase).where(*filters))
        rows = (
            await self.db.execute(
                select(EvalCase)
                .where(*filters)
                .order_by(EvalCase.sort_index.asc(), EvalCase.created_at.asc())
                .offset((params.page - 1) * params.size)
                .limit(params.size)
            )
        ).scalars().all()
        return PageResult(
            items=[EvalCaseOut.model_validate(r) for r in rows],
            total=total or 0,
            page=params.page,
            size=params.size,
        )

    async def create_case(self, dataset_id: UUID, body: EvalCaseCreate) -> EvalCaseOut:
        await self._get_dataset(dataset_id)
        row = EvalCase(
            tenant_id=self.ctx.tenant_id,
            dataset_id=dataset_id,
            name=(body.name.strip() if body.name else None),
            query=body.query.strip(),
            expected=body.expected,
            sort_index=body.sort_index,
        )
        self.db.add(row)
        await self.db.flush()
        return EvalCaseOut.model_validate(row)

    async def update_case(self, dataset_id: UUID, case_id: UUID, body: EvalCaseUpdate) -> EvalCaseOut:
        row = await self._get_case(dataset_id, case_id)
        if body.query is not None:
            row.query = body.query.strip()
        if body.name is not None:
            row.name = body.name.strip() if body.name else None
        if body.expected is not None:
            row.expected = body.expected
        if body.sort_index is not None:
            row.sort_index = body.sort_index
        await self.db.flush()
        return EvalCaseOut.model_validate(row)

    async def delete_case(self, dataset_id: UUID, case_id: UUID) -> None:
        row = await self._get_case(dataset_id, case_id)
        await self.db.delete(row)
        await self.db.flush()

    # --- run ---

    async def create_run(self, body: EvalRunCreate) -> EvalRunOut:
        await self._get_dataset(body.dataset_id)
        agent = await self.db.get(Agent, body.agent_id)
        if not agent or is_marked_deleted(agent):
            raise NotFoundError("智能体不存在")
        assert_tenant_access(self.ctx, agent.tenant_id)
        case_count = await self.db.scalar(
            select(func.count()).select_from(EvalCase).where(
                EvalCase.dataset_id == body.dataset_id,
                EvalCase.tenant_id == self.ctx.tenant_id,
            )
        )
        if not case_count:
            raise BadRequestError("数据集没有用例")

        run = EvalRun(
            tenant_id=self.ctx.tenant_id,
            dataset_id=body.dataset_id,
            agent_id=body.agent_id,
            status=EvalRunStatus.PENDING.value,
            scoring_mode=body.scoring_mode,
            created_by=self.ctx.user_id,
            summary={},
        )
        self.db.add(run)
        await self.db.flush()

        cases = (
            await self.db.execute(
                select(EvalCase)
                .where(
                    EvalCase.dataset_id == body.dataset_id,
                    EvalCase.tenant_id == self.ctx.tenant_id,
                )
                .order_by(EvalCase.sort_index.asc())
            )
        ).scalars().all()
        for case in cases:
            self.db.add(
                EvalRunItem(
                    tenant_id=self.ctx.tenant_id,
                    run_id=run.id,
                    case_id=case.id,
                    status="pending",
                    score_detail={},
                )
            )
        await self.db.flush()
        return EvalRunOut.model_validate(run)

    async def start_run(self, run_id: UUID) -> EvalRunOut:
        run = await self._get_run(run_id)
        if run.status not in (EvalRunStatus.PENDING.value, EvalRunStatus.FAILED.value):
            raise BadRequestError(f"当前状态不可启动: {run.status}")
        run.status = EvalRunStatus.PENDING.value
        run.error_message = None
        await self.db.flush()
        await self.db.commit()
        celery_app.send_task(RUN_EVAL_BATCH, args=[str(run.id)])
        return EvalRunOut.model_validate(run)

    async def get_run(self, run_id: UUID) -> EvalRunOut:
        return EvalRunOut.model_validate(await self._get_run(run_id))

    async def list_runs(self, params: PageParams, *, dataset_id: UUID | None = None) -> PageResult[EvalRunOut]:
        filters = [EvalRun.tenant_id == self.ctx.tenant_id]
        if dataset_id is not None:
            filters.append(EvalRun.dataset_id == dataset_id)
        total = await self.db.scalar(select(func.count()).select_from(EvalRun).where(*filters))
        rows = (
            await self.db.execute(
                select(EvalRun)
                .where(*filters)
                .order_by(EvalRun.created_at.desc())
                .offset((params.page - 1) * params.size)
                .limit(params.size)
            )
        ).scalars().all()
        return PageResult(
            items=[EvalRunOut.model_validate(r) for r in rows],
            total=total or 0,
            page=params.page,
            size=params.size,
        )

    async def list_run_items(self, run_id: UUID, params: PageParams) -> PageResult[EvalRunItemOut]:
        await self._get_run(run_id)
        filters = [EvalRunItem.run_id == run_id, EvalRunItem.tenant_id == self.ctx.tenant_id]
        total = await self.db.scalar(select(func.count()).select_from(EvalRunItem).where(*filters))
        rows = (
            await self.db.execute(
                select(EvalRunItem)
                .where(*filters)
                .order_by(EvalRunItem.created_at.asc())
                .offset((params.page - 1) * params.size)
                .limit(params.size)
            )
        ).scalars().all()
        return PageResult(
            items=[EvalRunItemOut.model_validate(r) for r in rows],
            total=total or 0,
            page=params.page,
            size=params.size,
        )

    # --- helpers ---

    async def _get_dataset(self, dataset_id: UUID) -> EvalDataset:
        row = await self.db.get(EvalDataset, dataset_id)
        if not row or is_marked_deleted(row):
            raise NotFoundError("数据集不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        return row

    async def _get_case(self, dataset_id: UUID, case_id: UUID) -> EvalCase:
        await self._get_dataset(dataset_id)
        row = await self.db.get(EvalCase, case_id)
        if not row or row.dataset_id != dataset_id:
            raise NotFoundError("用例不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        return row

    async def _get_run(self, run_id: UUID) -> EvalRun:
        row = await self.db.get(EvalRun, run_id)
        if not row:
            raise NotFoundError("评测运行不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        return row

    async def _case_counts(self, dataset_ids: set[UUID]) -> dict[UUID, int]:
        if not dataset_ids:
            return {}
        rows = (
            await self.db.execute(
                select(EvalCase.dataset_id, func.count())
                .where(EvalCase.dataset_id.in_(dataset_ids))
                .group_by(EvalCase.dataset_id)
            )
        ).all()
        return {did: int(cnt) for did, cnt in rows}

    @staticmethod
    def _dataset_out(row: EvalDataset, case_count: int) -> EvalDatasetOut:
        return EvalDatasetOut(
            id=row.id,
            tenant_id=row.tenant_id,
            name=row.name,
            description=row.description,
            created_at=row.created_at,
            case_count=case_count,
        )
