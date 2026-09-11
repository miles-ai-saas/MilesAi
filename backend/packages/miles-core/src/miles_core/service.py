"""业务服务基类。

租户域 Service 通常注入 (db, ctx)；AuthService 等可无 ctx。
"""

from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.tenant import TenantContext


class BaseService:
    """持有 AsyncSession 与可选 TenantContext。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext | None = None) -> None:
        self.db = db
        self.ctx = ctx
