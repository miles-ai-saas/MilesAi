"""业务中心 RBAC seed 单元测试。"""

from scripts.seed.biz_roles import BIZ_PERMISSIONS, BIZ_ROLE_SPECS


def test_biz_permissions_cover_api_modules():
    codes = {code for code, _, _ in BIZ_PERMISSIONS}
    for required in (
        "biz:dashboard:read",
        "biz:client:read",
        "biz:client:write",
        "biz:opportunity:read",
        "biz:project:read",
        "biz:project:write",
        "biz:contract:read",
        "biz:payment:read",
        "biz:supplier:read",
    ):
        assert required in codes


def test_biz_role_specs_reference_valid_permissions():
    valid = {code for code, _, _ in BIZ_PERMISSIONS}
    for spec in BIZ_ROLE_SPECS:
        for code in spec["permissions"]:
            assert code in valid, f"{spec['code']} references unknown permission {code}"
