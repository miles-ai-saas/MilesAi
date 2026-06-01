"""平台域 ORM：租户、用户、角色权限、系统配置（sys_* 表）。"""

from app.models.platform.role import Permission, Role, role_permissions, user_roles
from app.models.platform.system import SystemConfig
from app.models.platform.tenant import Tenant, TenantStatus
from app.models.platform.user import User

__all__ = [
    "TenantStatus",
    "Tenant",
    "User",
    "Role",
    "Permission",
    "user_roles",
    "role_permissions",
    "SystemConfig",
]
