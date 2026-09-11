"""租户系统仓储包导出。"""

from miles_portal.tenant.system.repositories.tenant import TenantRepository
from miles_portal.tenant.system.repositories.user import UserRepository

__all__ = ["TenantRepository", "UserRepository"]
