"""智能体 runtime_mode / planner 与子智能体 role_hint 枚举（re-export）。

定义已下沉中立域 ``miles_core.models.agent.constants``；本模块保持既有引用路径
（``agents/meta.py``、``a2a/services/host_bindings.py``、``services/sub_agents.py`` 等 L1 内部），
禁止再在 L3/新代码 import 本模块——L3 应指向 ``miles_core.models.agent.constants``。
"""

from miles_core.models.agent.constants import (
    SUB_AGENT_ROLE_DISPLAY,
    SUB_AGENT_ROLE_HINTS,
    SUB_AGENT_ROLE_LABELS,
    AgentPlanner,
    AgentRuntimeMode,
    SubAgentRoleHint,
)

__all__ = [
    "AgentRuntimeMode",
    "AgentPlanner",
    "SubAgentRoleHint",
    "SUB_AGENT_ROLE_HINTS",
    "SUB_AGENT_ROLE_DISPLAY",
    "SUB_AGENT_ROLE_LABELS",
]
