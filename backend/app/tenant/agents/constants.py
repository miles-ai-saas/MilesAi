"""子智能体 role_hint 取值与展示文案（校验、meta、DeepAgents 共用）。"""

import enum


class SubAgentRoleHint(str, enum.Enum):
    RETRIEVAL = "retrieval"
    OCR = "ocr"
    SUMMARY = "summary"
    COMPLIANCE = "compliance"
    CUSTOM = "custom"


class SubAgentPlanner(str, enum.Enum):
    """有子智能体绑定时 ``agent.config.planner`` 取值。"""

    DEEPAGENTS = "deepagents"
    PLATFORM = "platform"


SUB_AGENT_ROLE_HINTS = frozenset(h.value for h in SubAgentRoleHint)

# value -> (label, hint)
SUB_AGENT_ROLE_DISPLAY: dict[str, tuple[str, str | None]] = {
    SubAgentRoleHint.RETRIEVAL.value: ("检索", "知识检索"),
    SubAgentRoleHint.OCR.value: ("OCR", "OCR 识别"),
    SubAgentRoleHint.SUMMARY.value: ("总结", "摘要归纳"),
    SubAgentRoleHint.COMPLIANCE.value: ("合规", "合规审查"),
    SubAgentRoleHint.CUSTOM.value: ("自定义", "自定义"),
}

# DeepAgents 子智能体描述（优先 hint 长文案）
SUB_AGENT_ROLE_LABELS: dict[str, str] = {
    role: (hint or label)
    for role, (label, hint) in SUB_AGENT_ROLE_DISPLAY.items()
}
