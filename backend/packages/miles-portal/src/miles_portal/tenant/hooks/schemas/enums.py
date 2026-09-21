"""钩子 API 侧枚举声明。

与 ORM 侧 ``miles_portal.tenant.hooks.models`` 逐字同形（成员名/顺序/值/类 docstring），因 API 声明层不得依赖 ORM 模块
（``.importlinter`` 契约 ``api-layer-no-orm``）而独立声明；两侧一致性由
``tests/test_api_enum_parity.py`` 守卫。
"""

import enum


class HookType(enum.StrEnum):
    HTTP = "http"
    PYTHON = "python"


class HookTrigger(enum.StrEnum):
    """挂载时机：调用、推理、工具、错误等关键节点。"""

    BEFORE_CALL = "before_call"
    AFTER_CALL = "after_call"
    BEFORE_REASONING = "before_reasoning"
    AFTER_REASONING = "after_reasoning"
    BEFORE_TOOL = "before_tool"
    AFTER_TOOL = "after_tool"
    ON_ERROR = "on_error"


class HookScope(enum.StrEnum):
    GLOBAL = "global"
    AGENT = "agent"
    FLOW = "flow"
    TOOL = "tool"
    APP = "app"
