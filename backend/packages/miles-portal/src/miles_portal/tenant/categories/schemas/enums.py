"""分类 API 侧枚举声明。

与 ORM 侧 ``miles_core.models.meta.category`` 逐字同形（成员名/顺序/值），因 API 声明层不得依赖 ORM 模块
（``.importlinter`` 契约 ``api-layer-no-orm``）而独立声明；两侧一致性由
``tests/models/test_api_enum_parity.py`` 守卫。
"""

import enum


class CategoryDomain(enum.StrEnum):
    """工作台资源域；与列表 Tab、校验时的 domain 参数一致。"""

    AGENT = "agent"
    PROMPT = "prompt"
    SKILL = "skill"
    TOOL = "tool"
