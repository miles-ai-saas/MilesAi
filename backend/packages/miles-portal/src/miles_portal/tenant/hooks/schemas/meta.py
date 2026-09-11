"""hooks 模块 GET */meta 响应体（与 tenant/hooks/meta.py 字段一致）。"""

from pydantic import BaseModel, Field

from miles_common.schemas.enum_meta import META_SCHEMA_VERSION, EnumOption


class HookMetaOut(BaseModel):
    """钩子触发器、作用域与失败策略枚举。"""

    triggers: list[EnumOption] = Field(description="触发时机枚举选项")
    scopes: list[EnumOption] = Field(description="作用域枚举选项")
    on_failure_options: list[EnumOption] = Field(description="失败处理策略枚举选项")
    response_actions: list[EnumOption] = Field(description="响应动作枚举选项")
    schema_version: str = Field(default=META_SCHEMA_VERSION, description="元数据 schema 版本")
