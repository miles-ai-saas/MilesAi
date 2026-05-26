"""合规扫描场景 module 取值（试跑 API、Hook、meta 共用）。"""

SCAN_MODULE_AGENT_CHAT = "agent_chat"
SCAN_MODULE_FLOW_RUN = "flow_run"
SCAN_MODULE_GENERATIVE = "generative"

COMPLIANCE_SCAN_MODULES = frozenset({
    SCAN_MODULE_AGENT_CHAT,
    SCAN_MODULE_FLOW_RUN,
    SCAN_MODULE_GENERATIVE,
})
