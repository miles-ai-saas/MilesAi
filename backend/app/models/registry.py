"""登记全部 ORM 模块，供 Alembic 与启动时加载 metadata。"""


def load_all_models() -> None:
    """按依赖顺序导入各域 models，避免在 models/__init__ 中循环引用。"""
    import app.models.platform  # noqa: F401 — sys_* 租户/用户/角色
    import app.models.kb  # noqa: F401 — kb_*
    import app.models.flow  # noqa: F401 — flow_*
    import app.models.model  # noqa: F401 — agt_model_* / generative
    import app.models.media  # noqa: F401 — 附件/媒体资产
    import app.models.meta  # noqa: F401 — 分类/标签
    import app.models.task  # noqa: F401 — task_records
    import app.models.storage  # noqa: F401 — 对象存储配置
    import app.models.agent  # noqa: F401 — agt_* 智能体
    import app.models  # noqa: F401 — 聚合 re-export（不新增表）
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
