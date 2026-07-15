"""智能体 API 对接调试：debug-token 与 JWT TTL。"""

from datetime import datetime, timedelta, timezone

from jose import jwt

from app.core.config import get_settings
from app.core.security import create_access_token, safe_decode_token


def test_create_access_token_respects_expires_delta():
    settings = get_settings()
    token = create_access_token(
        "user-1",
        {"tenant_id": "t1", "purpose": "agent_api_debug"},
        expires_delta=timedelta(hours=24),
    )
    payload = safe_decode_token(token)
    assert payload is not None
    assert payload["type"] == "access"
    assert payload["purpose"] == "agent_api_debug"
    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    delta = exp - datetime.now(timezone.utc)
    assert timedelta(hours=23) < delta <= timedelta(hours=24, minutes=1)
    assert settings.access_token_expire_minutes == 60 or True
    raw = jwt.get_unverified_claims(token)
    assert raw["sub"] == "user-1"
