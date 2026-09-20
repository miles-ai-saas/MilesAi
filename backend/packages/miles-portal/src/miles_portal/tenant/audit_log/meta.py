"""审计日志枚举展示元数据（GET /audit/meta）。

- ``resource_type_filters`` / ``action_filters``：列表页筛选下拉（含「全部」空值）
- ``resource_types`` / ``action_labels``：表格列展示文案
- 前端：lib/audit-labels.ts、hooks/use-audit-meta.ts、system/audit 页
- 约定：docs/guides/hooks.md §9
"""

from miles_common.schemas.enum_meta import META_SCHEMA_VERSION, literal_options

# 筛选「全部」+ 常见 resource_type（与 write_tenant_audit_log 约定一致，可扩展）
RESOURCE_TYPE_OPTIONS: list[tuple[str, str, str | None]] = [
    ("", "全部资源", None),
    ("agent", "智能体", None),
    ("prompt", "提示词", None),
    ("skill", "技能包", None),
    ("tool", "工具", None),
    ("kb", "知识库", None),
    ("flow", "流程", None),
    ("hook", "钩子", None),
    ("compliance", "合规", None),
    ("marketplace", "应用市场", None),
    ("attachment", "附件", None),
    ("user", "用户", None),
    ("role", "角色", None),
]

# 动作筛选建议（精确匹配 API action 参数；空值为全部）
ACTION_FILTER_OPTIONS: list[tuple[str, str, str | None]] = [
    ("", "全部动作", None),
    ("agent.create", "创建智能体", None),
    ("agent.update", "更新智能体", None),
    ("agent.delete", "删除智能体", None),
    ("kb.document.upload", "上传文档", None),
    ("kb.document.delete", "删除文档", None),
    ("flow.publish", "发布流程", None),
    ("compliance.scan", "合规试跑", None),
    ("a2a.message.send", "A2A 调用智能体", None),
    ("a2a.message.stream", "A2A 流式调用智能体", None),
    ("a2a.tasks.get", "A2A 查询任务", None),
    ("a2a.tasks.cancel", "A2A 取消任务", None),
    ("a2a.artifact.download", "A2A 下载任务产物", None),
    ("auth.login", "用户登录", None),
    ("user.create", "创建用户", None),
    ("user.update", "更新用户", None),
    ("user.deactivate", "删除用户", None),
    ("user.reset_password", "重置密码", None),
]

# 展示用动作文案（未知 action 仍回显原值）
ACTION_LABELS: list[tuple[str, str, str | None]] = [(v, lb, h) for v, lb, h in ACTION_FILTER_OPTIONS if v]


def audit_meta_dict() -> dict:
    """构建 meta 响应 dict，供 *MetaOut.model_validate 与单测使用。"""
    return {
        "resource_types": literal_options([(v, lb, h) for v, lb, h in RESOURCE_TYPE_OPTIONS if v]),
        "resource_type_filters": literal_options(RESOURCE_TYPE_OPTIONS),
        "action_filters": literal_options(ACTION_FILTER_OPTIONS),
        "action_labels": literal_options(ACTION_LABELS),
        "schema_version": META_SCHEMA_VERSION,
    }
