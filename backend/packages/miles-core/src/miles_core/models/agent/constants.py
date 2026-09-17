"""智能体运行时配置枚举/常量（中立域，L3/tenant 共用）。

``agent.config`` 键取值与子智能体 role_hint 的纯描述，供校验、meta、编排与
``integrations/deepagents``/``langgraph`` 适配层共用；L1 侧经
``tenant.agents.constants`` re-export（路径稳定）。

- ``AgentRuntimeMode``：``config.runtime_mode``
- ``AgentPlanner``：``config.planner``
- ``SubAgentRoleHint`` / ``SUB_AGENT_ROLE_*``：子智能体 ``role_hint`` 校验与展示
"""

import enum


class AgentRuntimeMode(enum.StrEnum):
    """``agent.config.runtime_mode``：RAG 与编排路径开关。"""

    LEGACY = "legacy"
    AUTONOMOUS = "autonomous"
    WORKFLOW = "workflow"


class AgentPlanner(enum.StrEnum):
    """``agent.config.planner``：子智能体 / A2A 宿主编排引擎。"""

    DEEPAGENTS = "deepagents"
    PLATFORM = "platform"
    A2A_ORCHESTRATOR = "a2a_orchestrator"


# 子智能体 role_hint 取值（用于校验与展示）。
class SubAgentRoleHint(enum.StrEnum):
    RETRIEVAL = "retrieval"
    OCR = "ocr"
    SUMMARY = "summary"
    COMPLIANCE = "compliance"
    CUSTOM = "custom"


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
SUB_AGENT_ROLE_LABELS: dict[str, str] = {role: (hint or label) for role, (label, hint) in SUB_AGENT_ROLE_DISPLAY.items()}
