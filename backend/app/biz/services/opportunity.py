"""商机 CRUD 服务。

商机是销售漏斗的核心实体，按照标准销售阶段流转：
  prospecting → qualification → proposal → negotiation → won / lost
赢单后可转为项目继续交付管理。
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.repositories.opportunity import OpportunityRepository
from app.biz.schemas.opportunity import (
    BizOpportunityCreate,
    BizOpportunityOut,
    BizOpportunityUpdate,
)
from app.common.exceptions import NotFoundError
from app.common.pagination import paginate
from app.common.schema import PageResult
from app.core.service import BaseService
from app.core.soft_delete import mark_deleted
from app.core.tenant import TenantContext, assert_tenant_access, tenant_filters
from app.models.biz import BizOpportunity


class OpportunityService(BaseService):
    """商机管理——支持按客户和阶段过滤的分页查询。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.repo = OpportunityRepository(db)

    async def list_opportunities(
        self, *, page: int = 1, size: int = 20, client_id: UUID | None = None, stage: str | None = None,
    ) -> PageResult[BizOpportunityOut]:
        """分页查询商机列表，可按客户、销售阶段过滤，按更新时间降序排列。"""
        filters = tenant_filters(self.ctx, BizOpportunity.tenant_id)
        if client_id:
            filters.append(BizOpportunity.client_id == client_id)
        if stage:
            filters.append(BizOpportunity.stage == stage)
        result = await paginate(
            self.db, BizOpportunity, page=page, size=size,
            filters=filters, order_by=BizOpportunity.updated_at.desc(),
        )
        return PageResult(
            items=[self._to_out(r) for r in result.items],
            total=result.total, page=result.page, size=result.size,
        )

    async def get(self, opp_id: UUID) -> BizOpportunityOut:
        """获取单个商机详情。"""
        return self._to_out(await self._get_or_raise(opp_id))

    async def create(self, body: BizOpportunityCreate) -> BizOpportunityOut:
        """创建商机，初始阶段默认为 prospecting，记录创建人。"""
        row = BizOpportunity(
            tenant_id=self.ctx.tenant_id,
            client_id=body.client_id,
            name=body.name.strip(),
            code=body.code.strip() if body.code else None,
            stage=body.stage,
            expected_value=body.expected_value,
            probability=body.probability,
            expected_close_date=body.expected_close_date,
            owner_id=body.owner_id,
            description=body.description,
            created_by=self.ctx.user_id,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return self._to_out(row)

    async def update(self, opp_id: UUID, body: BizOpportunityUpdate) -> BizOpportunityOut:
        """编辑商机信息，支持修改名称、阶段、预估金额/概率等。"""
        row = await self._get_or_raise(opp_id)
        for f in ("name", "code", "stage", "expected_value", "probability", "expected_close_date", "owner_id", "description"):
            val = getattr(body, f, None)
            if val is not None:
                setattr(row, f, val.strip() if isinstance(val, str) and f in ("name", "code") else val)
        await self.db.flush()
        await self.db.refresh(row)
        return self._to_out(row)

    async def delete(self, opp_id: UUID) -> None:
        """软删除商机（仅标记 deleted_at）。"""
        row = await self._get_or_raise(opp_id)
        await mark_deleted(self.db, row)

    def _to_out(self, row: BizOpportunity) -> BizOpportunityOut:
        return BizOpportunityOut(
            id=row.id, client_id=row.client_id, name=row.name,
            stage=row.stage, code=row.code,
            expected_value=row.expected_value, probability=row.probability,
            expected_close_date=row.expected_close_date,
            owner_id=row.owner_id, description=row.description,
            converted_to_project_id=row.converted_to_project_id,
        )

    async def _get_or_raise(self, opp_id: UUID) -> BizOpportunity:
        row = await self.repo.get_by_id(opp_id)
        if not row:
            raise NotFoundError("商机不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        return row
