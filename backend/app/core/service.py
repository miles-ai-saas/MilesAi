"""业务服务基类。"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import TenantContext


class BaseService:
    def __init__(self, db: AsyncSession, ctx: TenantContext | None = None) -> None:
        self.db = db
        self.ctx = ctx
