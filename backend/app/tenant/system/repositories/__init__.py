"""租户系统仓储包导出。"""

from app.tenant.system.repositories.tenant import TenantRepository
from app.tenant.system.repositories.user import UserRepository

__all__ = ["TenantRepository", "UserRepository"]
