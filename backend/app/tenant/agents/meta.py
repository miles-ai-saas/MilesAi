"""智能体枚举展示元数据（GET /agents/meta）。

- statuses / agent_types / primary_paths / sub_agent_role_hints
- SUB_AGENT_ROLE_* 与 integrations.deepagents.subagent_graphs 共用
- 前端：lib/agent-labels.ts、hooks/use-agent-meta.ts
"""

from app.common.schemas.enum_meta import EnumOption, enum_options, literal_options
from app.models.agent import AgentStatus, AgentType
from app.tenant.agents.schemas.architecture import PRIMARY_PATH_LABELS

AGENT_STATUS_LABELS: dict[str, tuple[str, str | None]] = {
    AgentStatus.ENABLED.value: ("启用", "可对话与调度"),
    AgentStatus.DISABLED.value: ("禁用", "保留配置，不可新对话"),
}

AGENT_TYPE_LABELS: dict[str, tuple[str, str | None]] = {
    AgentType.CUSTOM.value: ("平台内", "本地编排：模型、知识库、流程、子智能体"),
    AgentType.A2A.value: ("A2A 互联宿主", "统一入口，编排已登记的外部 Agent"),
}

# 与 integrations.deepagents.subagent_graphs 共用；空 value 表示未指定
SUB_AGENT_ROLE_OPTIONS: list[tuple[str, str, str | None]] = [
    ("", "未指定", None),
    ("retrieval", "检索", "知识检索"),
    ("ocr", "OCR", "OCR 识别"),
    ("summary", "总结", "摘要归纳"),
    ("compliance", "合规", "合规审查"),
    ("custom", "自定义", "自定义"),
]

# DeepAgents 子智能体描述（优先 hint 长文案）
SUB_AGENT_ROLE_LABELS: dict[str, str] = {
    value: (hint or label)
    for value, label, hint in SUB_AGENT_ROLE_OPTIONS
    if value
}


def agents_meta_dict() -> dict:
    """构建 meta 响应 dict，供 *MetaOut.model_validate 与单测使用。"""
    primary_paths = [
        EnumOption(value=key, label=label, hint=None)
        for key, label in PRIMARY_PATH_LABELS.items()
    ]
    return {
        "statuses": enum_options(AgentStatus, AGENT_STATUS_LABELS),
        "agent_types": enum_options(AgentType, AGENT_TYPE_LABELS),
        "sub_agent_role_hints": literal_options(SUB_AGENT_ROLE_OPTIONS),
        "primary_paths": primary_paths,
        "schema_version": "1",
    }
