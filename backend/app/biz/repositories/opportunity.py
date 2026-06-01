"""商机与合同仓储。"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import BaseRepository
from app.models.biz import BizContract, BizOpportunity


class OpportunityRepository(BaseRepository[BizOpportunity]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, BizOpportunity)


class ContractRepository(BaseRepository[BizContract]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, BizContract)
