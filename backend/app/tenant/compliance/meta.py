"""合规枚举展示元数据（GET /compliance/meta）。

- sensitive_actions：敏感词命中策略（warn / block）
- scan_modules：试跑/扫描场景（agent_chat / flow_run）
- 前端：lib/compliance-labels.ts、hooks/use-compliance-meta.ts
- 约定：docs/guides/hooks.md §9
"""

from app.common.schemas.enum_meta import META_SCHEMA_VERSION, enum_options, literal_options
from app.tenant.compliance.constants import (
    SCAN_MODULE_AGENT_CHAT,
    SCAN_MODULE_FLOW_RUN,
    SCAN_MODULE_GENERATIVE,
)
from app.tenant.compliance.models import SensitiveAction

SENSITIVE_ACTION_LABELS: dict[str, tuple[str, str | None]] = {
    SensitiveAction.WARN.value: ("警告", "记录日志，不阻断请求"),
    SensitiveAction.BLOCK.value: ("拦截", "拒绝请求并写入拦截日志"),
}

SCAN_MODULE_OPTIONS: list[tuple[str, str, str | None]] = [
    (SCAN_MODULE_AGENT_CHAT, "智能体对话", None),
    (SCAN_MODULE_FLOW_RUN, "流程运行", None),
    (SCAN_MODULE_GENERATIVE, "生图/生视频", "生成类 prompt 与工具调用"),
]


def compliance_meta_dict() -> dict:
    """构建 meta 响应 dict，供 *MetaOut.model_validate 与单测使用。"""
    return {
        "sensitive_actions": enum_options(SensitiveAction, SENSITIVE_ACTION_LABELS),
        "scan_modules": literal_options(SCAN_MODULE_OPTIONS),
        "schema_version": META_SCHEMA_VERSION,
    }
