"""合规扫描场景常量（re-export shim）。

实现已下沉中立域 ``app.models.compliance.constants``；保留本路径供 L1 既有引用
（``tenant.compliance.meta``、``tenant.flows.services.flow``、``tenant.agents.*`` 等）。
"""

from app.models.compliance.constants import (  # noqa: F401
    COMPLIANCE_SCAN_MODULES,
    SCAN_MODULE_AGENT_CHAT,
    SCAN_MODULE_FLOW_RUN,
    SCAN_MODULE_GENERATIVE,
)
