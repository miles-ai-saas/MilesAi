"""合规枚举展示元数据（GET /compliance/meta）。

- sensitive_actions：敏感词命中策略（warn / block）
- scan_modules：试跑/扫描场景（agent_chat / flow_run）
- 前端：lib/compliance-labels.ts、hooks/use-compliance-meta.ts
- 约定：docs/guides/hooks.md §9
"""

from app.common.schemas.enum_meta import literal_options

SENSITIVE_ACTION_OPTIONS: list[tuple[str, str, str | None]] = [
    ("warn", "警告", "记录日志，不阻断请求"),
    ("block", "拦截", "拒绝请求并写入拦截日志"),
]

SCAN_MODULE_OPTIONS: list[tuple[str, str, str | None]] = [
    ("agent_chat", "智能体对话", None),
    ("flow_run", "流程运行", None),
]


def compliance_meta_dict() -> dict:
    """构建 meta 响应 dict，供 *MetaOut.model_validate 与单测使用。"""
    return {
        "sensitive_actions": literal_options(SENSITIVE_ACTION_OPTIONS),
        "scan_modules": literal_options(SCAN_MODULE_OPTIONS),
    }
