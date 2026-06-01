"""合同 CRUD 服务。

合同与项目和客户绑定，支持四种类型：服务合同、保密协议、框架协议、其他
生命周期：draft → pending_sign → signed → active → completed / terminated
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.biz.repositories.opportunity import ContractRepository
from app.biz.schemas.contract import BizContractCreate, BizContractOut, BizContractUpdate
from app.common.exceptions import NotFoundError
from app.common.pagination import paginate
from app.common.schema import PageResult
from app.core.service import BaseService
from app.core.soft_delete import mark_deleted
from app.core.tenant import TenantContext, assert_tenant_access, tenant_filters
from app.models.biz import BizContract


class ContractService(BaseService):
    """合同管理——支持按项目和状态过滤，与收付款联动。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)
        self.repo = ContractRepository(db)

    async def list_contracts(
        self, *, page: int = 1, size: int = 20, project_id: UUID | None = None, client_id: UUID | None = None, status: str | None = None,
    ) -> PageResult[BizContractOut]:
        """分页查询合同列表，可按所属项目、客户、合同状态过滤。"""
        filters = tenant_filters(self.ctx, BizContract.tenant_id)
        if project_id:
            filters.append(BizContract.project_id == project_id)
        if client_id:
            filters.append(BizContract.client_id == client_id)
        if status:
            filters.append(BizContract.status == status)
        result = await paginate(
            self.db, BizContract, page=page, size=size,
            filters=filters, order_by=BizContract.updated_at.desc(),
        )
        return PageResult(
            items=[self._to_out(r) for r in result.items],
            total=result.total, page=result.page, size=result.size,
        )

    async def get(self, contract_id: UUID) -> BizContractOut:
        """获取单个合同详情（含金额、付款条款、期限）。"""
        return self._to_out(await self._get_or_raise(contract_id))

    async def create(self, body: BizContractCreate) -> BizContractOut:
        """创建合同，需绑定项目和客户，默认状态为 draft。"""
        row = BizContract(
            tenant_id=self.ctx.tenant_id,
            project_id=body.project_id,
            client_id=body.client_id,
            name=body.name.strip(),
            contract_no=body.contract_no.strip() if body.contract_no else None,
            type=body.type,
            signed_date=body.signed_date,
            start_date=body.start_date,
            end_date=body.end_date,
            total_amount=body.total_amount,
            payment_terms=body.payment_terms,
            description=body.description,
            created_by=self.ctx.user_id,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return self._to_out(row)

    async def update(self, contract_id: UUID, body: BizContractUpdate) -> BizContractOut:
        """编辑合同信息，支持修改名称、编号、类型、状态、金额等。"""
        row = await self._get_or_raise(contract_id)
        for f in ("name", "contract_no", "type", "status", "signed_date", "start_date", "end_date", "total_amount", "payment_terms", "description"):
            val = getattr(body, f, None)
            if val is not None:
                setattr(row, f, val.strip() if isinstance(val, str) and f in ("name", "contract_no") else val)
        await self.db.flush()
        await self.db.refresh(row)
        return self._to_out(row)

    async def delete(self, contract_id: UUID) -> None:
        """软删除合同（仅标记 deleted_at，收付款记录不受影响）。"""
        row = await self._get_or_raise(contract_id)
        await mark_deleted(self.db, row)

    def _to_out(self, row: BizContract) -> BizContractOut:
        return BizContractOut(
            id=row.id, project_id=row.project_id, client_id=row.client_id,
            name=row.name, status=row.status, type=row.type,
            contract_no=row.contract_no,
            signed_date=row.signed_date, start_date=row.start_date, end_date=row.end_date,
            total_amount=row.total_amount, payment_terms=row.payment_terms,
            description=row.description,
        )

    async def _get_or_raise(self, contract_id: UUID) -> BizContract:
        row = await self.repo.get_by_id(contract_id)
        if not row:
            raise NotFoundError("合同不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        return row
