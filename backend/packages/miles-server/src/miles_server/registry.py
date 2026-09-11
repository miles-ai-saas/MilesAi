"""登记全部 ORM 模块，供 Alembic 与启动时加载 metadata。

位于装配层（miles_server）：需汇总各域 ORM，不得下沉到 miles_core。
"""


def load_all_models() -> None:
    """按依赖顺序导入各域 models，避免在 models/__init__ 中循环引用。"""
    import miles_core.models.platform  # noqa: F401 — sys_* 租户/用户/角色
    import miles_core.models.kb  # noqa: F401 — kb_*
    import miles_core.models.flow  # noqa: F401 — flow_*
    import miles_core.models.model  # noqa: F401 — agt_model_* / generative
    import miles_core.models.media  # noqa: F401 — 附件/媒体资产
    import miles_core.models.meta  # noqa: F401 — 分类/标签
    import miles_core.models.task  # noqa: F401 — task_records
    import miles_core.models.storage  # noqa: F401 — 对象存储配置
    import miles_core.models.agent  # noqa: F401 — agt_* 智能体
    import miles_core.models.marketplace  # noqa: F401 — mkt_* 市场（admin/tenant 共读）
    import miles_core.models.risk  # noqa: F401 — 风控表（adm_risk_events / adm_ip_blacklist / adm_rate_limit_rules）
    import miles_core.models  # noqa: F401 — 聚合 re-export（不新增表）
    import miles_admin.models  # noqa: F401
    import miles_portal.tenant.compliance.models  # noqa: F401
    import miles_portal.tenant.hooks.models  # noqa: F401
    import miles_portal.tenant.prompts.models  # noqa: F401
    import miles_portal.tenant.skills.models  # noqa: F401
    import miles_portal.tenant.mcp.models  # noqa: F401
    import miles_portal.tenant.a2a.models  # noqa: F401
    import miles_portal.tenant.tools.models  # noqa: F401
    import miles_portal.tenant.audit_log.models  # noqa: F401
