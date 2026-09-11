"""租户、权限、默认管理员账号。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.config import get_settings
from miles_core.security import hash_password
from miles_core.models import Permission, Role, Tenant, User
from miles_core.models.platform.role import role_permissions, user_roles

DEFAULT_PERMISSIONS = [
    ("system:tenant:read", "查看租户", "system"),
    ("system:tenant:write", "管理租户", "system"),
    ("system:user:read", "查看用户", "system"),
    ("system:user:write", "管理用户", "system"),
    ("system:config:read", "查看配置", "system"),
    ("system:config:write", "管理配置", "system"),
    ("system:role:read", "查看角色", "system"),
    ("system:role:write", "管理角色", "system"),
    ("system:session:read", "查看会话", "system"),
    ("system:session:write", "管理会话", "system"),
    ("system:quota:read", "查看资源配额", "system"),
    ("compliance:read", "查看合规", "compliance"),
    ("compliance:write", "管理合规", "compliance"),
    ("prompt:read", "查看提示词模版", "prompt"),
    ("prompt:write", "管理提示词模版", "prompt"),
    ("model:read", "查看模型供应商", "model"),
    ("model:write", "管理模型供应商", "model"),
    ("agent:read", "查看智能体", "agent"),
    ("agent:write", "管理智能体", "agent"),
    ("hook:read", "查看钩子", "hook"),
    ("hook:write", "管理钩子", "hook"),
    ("tools:read", "查看工具", "tools"),
    ("tools:write", "管理工具", "tools"),
    ("skill:read", "查看技能包", "skill"),
    ("skill:write", "管理技能包", "skill"),
    ("tag:read", "查看标签", "tag"),
    ("tag:write", "管理标签", "tag"),
    ("mcp:read", "查看 MCP", "mcp"),
    ("mcp:write", "管理 MCP", "mcp"),
    ("kb:read", "查看知识库", "kb"),
    ("kb:write", "管理知识库", "kb"),
    ("kb:document:upload", "上传文档", "kb"),
    ("attachment:read", "查看附件", "attachment"),
    ("attachment:write", "管理附件", "attachment"),
    ("attachment:upload", "上传附件", "attachment"),
    ("flow:read", "查看流程", "flow"),
    ("flow:write", "管理流程", "flow"),
    ("task:read", "查看任务", "task"),
    ("task:write", "管理任务", "task"),
    ("monitor:read", "查看监控", "monitor"),
    ("monitor:write", "管理监控", "monitor"),
    ("marketplace:read", "查看应用市场", "marketplace"),
    ("marketplace:write", "发布应用", "marketplace"),
    ("marketplace:install", "安装应用", "marketplace"),
    ("marketplace:review", "审核应用上架", "marketplace"),
    ("marketplace:rate", "评价应用", "marketplace"),
    ("audit:read", "查看审计日志", "audit"),
]


TENANT_ADMIN_PERMISSION_PREFIX_DENY = ("system:tenant:",)


async def ensure_tenant_permissions(session: AsyncSession) -> None:
    """幂等补齐权限，并挂到 super_admin / 各租户 tenant_admin 角色。"""
    perm_by_code: dict[str, Permission] = {}
    for code, name, module in DEFAULT_PERMISSIONS:
        row = await session.scalar(select(Permission).where(Permission.code == code))
        if not row:
            row = Permission(code=code, name=name, module=module)
            session.add(row)
            await session.flush()
        perm_by_code[code] = row

    async def _grant_role(role: Role, codes: set[str]) -> None:
        linked = set(await session.scalars(select(role_permissions.c.permission_id).where(role_permissions.c.role_id == role.id)))
        for code in codes:
            perm = perm_by_code.get(code)
            if perm and perm.id not in linked:
                await session.execute(role_permissions.insert().values(role_id=role.id, permission_id=perm.id))

    super_admin = await session.scalar(select(Role).where(Role.code == "super_admin"))
    if super_admin:
        await _grant_role(super_admin, set(perm_by_code.keys()))

    tenant_admin_roles = (await session.scalars(select(Role).where(Role.code == "tenant_admin"))).all()
    tenant_codes = {c for c in perm_by_code if not c.startswith(TENANT_ADMIN_PERMISSION_PREFIX_DENY)}
    for role in tenant_admin_roles:
        await _grant_role(role, tenant_codes)


async def seed_tenant(session: AsyncSession) -> None:
    settings = get_settings()

    await ensure_tenant_permissions(session)

    existing = await session.execute(select(User).where(User.username == settings.seed_admin_username))
    if existing.scalar_one_or_none():
        await session.flush()
        return

    permissions = (await session.execute(select(Permission).where(Permission.code.in_([c for c, _, _ in DEFAULT_PERMISSIONS])))).scalars().all()

    tenant = Tenant(name=settings.seed_tenant_name, description="系统默认租户")
    session.add(tenant)
    await session.flush()

    admin_role = Role(
        tenant_id=None,
        name="超级管理员",
        code="super_admin",
        description="拥有全部权限",
        is_system=True,
    )
    session.add(admin_role)
    await session.flush()

    for perm in permissions:
        await session.execute(role_permissions.insert().values(role_id=admin_role.id, permission_id=perm.id))

    admin_user = User(
        tenant_id=tenant.id,
        username=settings.seed_admin_username,
        email=settings.seed_admin_email,
        hashed_password=hash_password(settings.seed_admin_password),
        is_active=True,
        is_superuser=True,
    )
    session.add(admin_user)
    await session.flush()

    await session.execute(user_roles.insert().values(user_id=admin_user.id, role_id=admin_role.id))

    tenant_admin = Role(
        tenant_id=tenant.id,
        name="租户管理员",
        code="tenant_admin",
        description="本租户内管理与配置权限",
        is_system=False,
    )
    session.add(tenant_admin)
    await session.flush()
    tenant_perm_codes = {c for c, _, _ in DEFAULT_PERMISSIONS if not c.startswith("system:tenant:")}
    for perm in permissions:
        if perm.code in tenant_perm_codes:
            await session.execute(role_permissions.insert().values(role_id=tenant_admin.id, permission_id=perm.id))
    await session.execute(user_roles.insert().values(user_id=admin_user.id, role_id=tenant_admin.id))

    # 分类为全平台全局字典，新租户无需 provision
