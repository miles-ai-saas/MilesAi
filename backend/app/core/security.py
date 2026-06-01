"""租户 JWT 与密码哈希（bcrypt）；运营端管理员令牌见 admin.app_sys.security。"""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings
from app.common.exceptions import UnauthorizedError
from app.models.platform.user import User

settings = get_settings()


def hash_password(password: str) -> str:
    """bcrypt 哈希，供 UserService.create_user 写入 hashed_password。"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """校验明文与库中哈希；格式异常时返回 False。"""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _encode(payload: dict[str, Any]) -> str:
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str, extra: dict[str, Any] | None = None) -> str:
    """签发 access JWT（type=access，含 tenant_id 等 extra）。"""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": subject,
        "type": "access",
        "exp": expire,
        "jti": str(uuid4()),
        **(extra or {}),
    }
    return _encode(payload)


def create_refresh_token(subject: str) -> str:
    """签发 refresh JWT（type=refresh，仅用于 /auth/refresh）。"""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    payload = {"sub": subject, "type": "refresh", "exp": expire, "jti": str(uuid4())}
    return _encode(payload)


def decode_token(token: str) -> dict[str, Any]:
    """解码 JWT；失败抛 UnauthorizedError（refresh 等需明确失败原因的路径）。"""
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise UnauthorizedError("无效或过期的令牌") from exc


def safe_decode_token(token: str) -> dict[str, Any] | None:
    """解码失败返回 None，供 get_current_user 区分无效令牌。"""
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


def token_extra_for_user(user: User) -> dict[str, Any]:
    """写入 access token payload 的租户与超管标记。"""
    return {"tenant_id": str(user.tenant_id), "is_superuser": user.is_superuser}


def issue_tokens_for_user(user: User) -> tuple[str, str]:
    """返回 (access_token, refresh_token) 对。"""
    subject = str(user.id)
    extra = token_extra_for_user(user)
    return create_access_token(subject, extra), create_refresh_token(subject)
