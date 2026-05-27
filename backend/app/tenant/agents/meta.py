"""智能体枚举展示元数据（GET /agents/meta）。

- statuses / agent_types / primary_paths / sub_agent_role_hints
- runtime_modes / planners：``agent.config`` 编排与 RAG 路径
- SUB_AGENT_ROLE_* 与 integrations.deepagents.subagent_graphs 共用
- 前端：lib/agent-labels.ts、hooks/use-agent-meta.ts
"""

from app.common.schemas.enum_meta import (
    META_SCHEMA_VERSION,
    EnumOption,
    enum_options,
    literal_options,
)
from app.models.agent import AgentStatus, AgentType
from app.tenant.agents.constants import (
    SUB_AGENT_ROLE_DISPLAY,
    SUB_AGENT_ROLE_HINTS,
    AgentPlanner,
    AgentRuntimeMode,
)
from app.tenant.agents.schemas.architecture import PRIMARY_PATH_LABELS

AGENT_STATUS_LABELS: dict[str, tuple[str, str | None]] = {
    AgentStatus.ENABLED.value: ("启用", "可对话与调度"),
    AgentStatus.DISABLED.value: ("禁用", "保留配置，不可新对话"),
}

AGENT_TYPE_LABELS: dict[str, tuple[str, str | None]] = {
    AgentType.CUSTOM.value: ("平台内", "本地编排：模型、知识库、流程、子智能体"),
    AgentType.A2A.value: ("A2A 互联宿主", "统一入口，编排已登记的外部 Agent"),
}

# 空 value 表示未指定
SUB_AGENT_ROLE_OPTIONS: list[tuple[str, str, str | None]] = [
    ("", "未指定", None),
    *[
        (role, *SUB_AGENT_ROLE_DISPLAY[role])
        for role in sorted(SUB_AGENT_ROLE_HINTS)
    ],
]

RUNTIME_MODE_LABELS: dict[str, tuple[str, str | None]] = {
    AgentRuntimeMode.LEGACY.value: ("线性 RAG", "强制走 LangChain 线性检索生成"),
    AgentRuntimeMode.AUTONOMOUS.value: ("自主编排", "子智能体 / A2A / DeepAgents"),
    AgentRuntimeMode.WORKFLOW.value: ("已发布流程", "走 published_flow_id 画布"),
}

PLANNER_LABELS: dict[str, tuple[str, str | None]] = {
    AgentPlanner.DEEPAGENTS.value: ("DeepAgents", "task 工具委派子智能体"),
    AgentPlanner.PLATFORM.value: ("平台规划器", "规则 + LLM 拆解子任务"),
    AgentPlanner.A2A_ORCHESTRATOR.value: ("A2A 编排", "外部 Peer 调用"),
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
        "runtime_modes": enum_options(AgentRuntimeMode, RUNTIME_MODE_LABELS),
        "planners": enum_options(AgentPlanner, PLANNER_LABELS),
        "schema_version": META_SCHEMA_VERSION,
    }
