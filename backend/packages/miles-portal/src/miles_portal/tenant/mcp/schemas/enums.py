"""MCP API 侧枚举声明。

与 ORM 侧 ``miles_portal.tenant.mcp.models`` 逐字同形（成员名/顺序/值/类 docstring），因 API 声明层不得依赖 ORM 模块
（``.importlinter`` 契约 ``api-layer-no-orm``）而独立声明；两侧一致性由
``tests/models/test_api_enum_parity.py`` 守卫。
"""

import enum


class McpStatus(enum.StrEnum):
    """同步与可用性状态，供工作台卡片展示。"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
