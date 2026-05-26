"""登记全部 ORM 模块，供 Alembic 与启动时加载 metadata。"""


def load_all_models() -> None:
    """按依赖顺序导入各域 models，避免在 models/__init__ 中循环引用。"""
    import app.models  # noqa: F401
    import app.models.agent_schedule  # noqa: F401
    import app.admin.models  # noqa: F401
    import app.tenant.compliance.models  # noqa: F401
    import app.tenant.hooks.models  # noqa: F401
    import app.tenant.prompts.models  # noqa: F401
    import app.tenant.skills.models  # noqa: F401
    import app.tenant.mcp.models  # noqa: F401
    import app.tenant.a2a.models  # noqa: F401
    import app.tenant.marketplace.models  # noqa: F401
    import app.tenant.tools.models  # noqa: F401
    import app.tenant.audit_log.models  # noqa: F401
