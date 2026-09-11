"""合规扫描枚举与场景常量（中立域，ORM/schemas/L3 共用）。

- ``SensitiveAction``：敏感词处置动作（warn/block）
- ``SCAN_MODULE_*`` / ``COMPLIANCE_SCAN_MODULES``：扫描场景 module 取值
  （试跑 API、Hook、meta、L3 生成面共用；L1 经 ``tenant.compliance.constants``
  re-export 保路径稳定）
"""

import enum

SCAN_MODULE_AGENT_CHAT = "agent_chat"
SCAN_MODULE_FLOW_RUN = "flow_run"
SCAN_MODULE_GENERATIVE = "generative"

COMPLIANCE_SCAN_MODULES = frozenset(
    {
        SCAN_MODULE_AGENT_CHAT,
        SCAN_MODULE_FLOW_RUN,
        SCAN_MODULE_GENERATIVE,
    }
)


class SensitiveAction(str, enum.Enum):
    """敏感词处置动作。"""

    WARN = "warn"
    BLOCK = "block"
