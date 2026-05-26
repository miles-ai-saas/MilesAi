"""hooks 模块 GET */meta 响应体（与 tenant/hooks/meta.py 字段一致）。"""

from pydantic import BaseModel

from app.common.schemas.enum_meta import EnumOption


class HookMetaOut(BaseModel):
    """钩子触发器、作用域与失败策略枚举。"""

    triggers: list[EnumOption]
    scopes: list[EnumOption]
    on_failure_options: list[EnumOption]
    response_actions: list[EnumOption]
    schema_version: str = "1"
