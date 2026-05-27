"""平台风控运行时单元测试。"""

from app.admin.app_ops.services.risk_enforce import PlatformRiskEnforcer


def test_match_path_wildcard():
    enforcer = PlatformRiskEnforcer()
    assert enforcer._match_path("/api/v1/*", "/api/v1/auth/login") is True
    assert enforcer._match_path("/api/v1/*", "/api/admin/v1/tenants") is False
