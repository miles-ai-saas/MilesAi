"""登记全部 ORM 模块，供 Alembic 与启动时加载 metadata。

位于装配层（miles_server）：需汇总各域 ORM，不得下沉到 miles_core。
"""

import importlib

# 需登记的全部 ORM 模块——导入即把表写进 ``Base.metadata``，无需引用其符号。
#
# 顺序无关：实测按本清单原序、字母序、逆序导入，三者都成功且都得到 65 张表，
# 故这里只按域罗列，不承担依赖排序职责。
#
# 清单过期是 fail-open：新增 ORM 模块而漏加一项，``Base.metadata`` 就缺表，而
# Alembic autogenerate 会把线上已有表判成待 DROP 的差异。完整性由
# ``tests/test_orm_registry_completeness.py`` 守住——漏加时该测试会失败。
_ORM_MODULES: tuple[str, ...] = (
    "miles_admin.models",
    "miles_core.models",  # 聚合 re-export（不新增表）
    "miles_core.models.agent",  # agt_* 智能体
    "miles_core.models.flow",  # flow_*
    "miles_core.models.kb",  # kb_*
    "miles_core.models.marketplace",  # mkt_* 市场（admin/tenant 共读）
    "miles_core.models.media",  # 附件/媒体资产
    "miles_core.models.meta",  # 分类/标签
    "miles_core.models.model",  # agt_model_* / generative
    "miles_core.models.platform",  # sys_* 租户/用户/角色
    "miles_core.models.risk",  # 风控表（adm_risk_events / adm_ip_blacklist / adm_rate_limit_rules）
    "miles_core.models.storage",  # 对象存储配置
    "miles_core.models.task",  # task_records
    "miles_portal.tenant.a2a.models",
    "miles_portal.tenant.audit_log.models",
    "miles_portal.tenant.compliance.models",
    "miles_portal.tenant.hooks.models",
    "miles_portal.tenant.mcp.models",
    "miles_portal.tenant.prompts.models",
    "miles_portal.tenant.skills.models",
    "miles_portal.tenant.tools.models",
)


def load_all_models() -> None:
    """导入 ``_ORM_MODULES`` 注册全部表；顺序无关，完整性由哨兵测试守住。"""
    for module in _ORM_MODULES:
        importlib.import_module(module)
