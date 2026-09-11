"""平台管理员 JWT（type=admin_access），与租户 access token 分离。"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from jose import jwt

from miles_core.config import get_settings
from miles_admin.models import PlatformAdmin

settings = get_settings()


def create_admin_access_token(admin: PlatformAdmin) -> str:
    """签发 type=admin_access JWT（含 role/username）。"""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(admin.id),
        "type": "admin_access",
        "username": admin.username,
        "role": admin.role,
        "exp": expire,
        "jti": str(uuid4()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
