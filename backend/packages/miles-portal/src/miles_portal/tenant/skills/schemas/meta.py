"""skills 模块 GET */meta 响应体（与 tenant/skills/meta.py 字段一致）。"""

from pydantic import BaseModel, Field

from miles_common.schemas.enum_meta import META_SCHEMA_VERSION, EnumOption


class SkillMetaOut(BaseModel):
    """技能包来源与启用状态枚举。"""

    source_types: list[EnumOption] = Field(description="技能包来源类型枚举")
    active_states: list[EnumOption] = Field(description="启用状态枚举")
    schema_version: str = Field(
        default=META_SCHEMA_VERSION,
        description="元数据 schema 版本",
    )
