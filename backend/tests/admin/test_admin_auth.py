"""运营后台 Phase 0 认证与会话测试。"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from miles_admin.app_sys.session_store import validate_admin_session


@pytest.mark.asyncio
async def test_validate_admin_session_ok():
    admin_id = uuid4()
    jti = "test-jti"
    with patch("miles_admin.app_sys.session_store.get_redis") as mock_redis_fn:
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=jti)
        mock_redis_fn.return_value = redis
        assert await validate_admin_session(admin_id, jti) is True


@pytest.mark.asyncio
async def test_validate_admin_session_mismatch():
    admin_id = uuid4()
    with patch("miles_admin.app_sys.session_store.get_redis") as mock_redis_fn:
        redis = AsyncMock()
        redis.get = AsyncMock(return_value="other-jti")
        mock_redis_fn.return_value = redis
        assert await validate_admin_session(admin_id, "token-jti") is False


@pytest.mark.asyncio
async def test_change_password_revokes_session():
    from miles_admin.app_sys.services.auth import AdminAuthService

    admin_id = uuid4()
    db = AsyncMock()
    svc = AdminAuthService(db)
    admin = AsyncMock()
    admin.hashed_password = "hash"
    svc.repo = AsyncMock()
    svc.repo.get_by_id_or_raise = AsyncMock(return_value=admin)

    with (
        patch("miles_admin.app_sys.services.auth.verify_password", return_value=True),
        patch("miles_admin.app_sys.services.auth.hash_password", return_value="newhash"),
        patch("miles_admin.app_sys.services.auth.revoke_admin_session", new_callable=AsyncMock) as revoke,
    ):
        from miles_admin.app_sys.schemas.auth import PasswordChangeRequest

        await svc.change_password(admin_id, PasswordChangeRequest(old_password="old", new_password="new123"))
        revoke.assert_awaited_once_with(admin_id)
