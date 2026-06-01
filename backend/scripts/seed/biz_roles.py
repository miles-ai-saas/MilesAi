"""业务中心 RBAC：biz:* 权限与试点角色 seed。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Permission, Role, Tenant
from app.models.platform.role import role_permissions

BIZ_PERMISSIONS: list[tuple[str, str, str]] = [
    ("biz:dashboard:read", "查看业务仪表盘", "biz"),
    ("biz:client:read", "查看客户", "biz"),
    ("biz:client:write", "管理客户", "biz"),
    ("biz:opportunity:read", "查看商机", "biz"),
    ("biz:opportunity:write", "管理商机", "biz"),
    ("biz:project:read", "查看项目", "biz"),
    ("biz:project:write", "管理项目", "biz"),
    ("biz:contract:read", "查看合同", "biz"),
    ("biz:contract:write", "管理合同", "biz"),
    ("biz:payment:read", "查看收付款", "biz"),
    ("biz:payment:write", "管理收付款", "biz"),
    ("biz:supplier:read", "查看供应商", "biz"),
    ("biz:supplier:write", "管理供应商", "biz"),
    ("biz:finance:read", "查看业务财务", "biz"),
]

BIZ_ROLE_SPECS: list[dict] = [
    {
        "code": "biz_gm",
        "name": "业务总经理",
        "description": "业务中心全部权限",
        "permissions": [code for code, _, _ in BIZ_PERMISSIONS],
    },
    {
        "code": "biz_sales",
        "name": "商务经理",
        "description": "客户与商机管理，项目只读",
        "permissions": [
            "biz:dashboard:read",
            "biz:client:read",
            "biz:client:write",
            "biz:opportunity:read",
            "biz:opportunity:write",
            "biz:project:read",
        ],
    },
    {
        "code": "biz_pm",
        "name": "项目经理",
        "description": "项目交付与客户/商机只读",
        "permissions": [
            "biz:dashboard:read",
            "biz:client:read",
            "biz:opportunity:read",
            "biz:project:read",
            "biz:project:write",
            "biz:supplier:read",
        ],
    },
    {
        "code": "biz_finance",
        "name": "业务财务",
        "description": "合同、收付款与成本相关只读/写入",
        "permissions": [
            "biz:dashboard:read",
            "biz:client:read",
            "biz:project:read",
            "biz:contract:read",
            "biz:contract:write",
            "biz:payment:read",
            "biz:payment:write",
            "biz:supplier:read",
            "biz:finance:read",
        ],
    },
]


async def _default_tenant_id(session: AsyncSession):
    settings = get_settings()
    return await session.scalar(select(Tenant.id).where(Tenant.name == settings.seed_tenant_name).limit(1))


async def ensure_biz_permissions(session: AsyncSession) -> dict[str, Permission]:
    """幂等补齐 biz:* 权限定义。"""
    perm_by_code: dict[str, Permission] = {}
    for code, name, module in BIZ_PERMISSIONS:
        row = await session.scalar(select(Permission).where(Permission.code == code))
        if not row:
            row = Permission(code=code, name=name, module=module)
            session.add(row)
            await session.flush()
        perm_by_code[code] = row
    return perm_by_code


async def seed_biz_roles(session: AsyncSession) -> None:
    """为默认租户创建业务中心试点角色并绑定权限。"""
    perm_by_code = await ensure_biz_permissions(session)
    tenant_id = await _default_tenant_id(session)
    if not tenant_id:
        return

    super_admin = await session.scalar(select(Role).where(Role.code == "super_admin"))
    if super_admin:
        linked = set(await session.scalars(select(role_permissions.c.permission_id).where(role_permissions.c.role_id == super_admin.id)))
        for perm in perm_by_code.values():
            if perm.id not in linked:
                await session.execute(role_permissions.insert().values(role_id=super_admin.id, permission_id=perm.id))

    tenant_admin = await session.scalar(
        select(Role).where(Role.tenant_id == tenant_id, Role.code == "tenant_admin")
    )
    if tenant_admin:
        linked = set(await session.scalars(select(role_permissions.c.permission_id).where(role_permissions.c.role_id == tenant_admin.id)))
        for perm in perm_by_code.values():
            if perm.id not in linked:
                await session.execute(role_permissions.insert().values(role_id=tenant_admin.id, permission_id=perm.id))

    for spec in BIZ_ROLE_SPECS:
        role = await session.scalar(
            select(Role).where(Role.tenant_id == tenant_id, Role.code == spec["code"])
        )
        if not role:
            role = Role(
                tenant_id=tenant_id,
                name=spec["name"],
                code=spec["code"],
                description=spec["description"],
                is_system=False,
            )
            session.add(role)
            await session.flush()

        linked = set(await session.scalars(select(role_permissions.c.permission_id).where(role_permissions.c.role_id == role.id)))
        for code in spec["permissions"]:
            perm = perm_by_code.get(code)
            if perm and perm.id not in linked:
                await session.execute(role_permissions.insert().values(role_id=role.id, permission_id=perm.id))

    await session.flush()
