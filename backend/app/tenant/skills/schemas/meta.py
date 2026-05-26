"""skills 模块 GET */meta 响应体（与 tenant/skills/meta.py 字段一致）。"""

from pydantic import BaseModel

from app.common.schemas.enum_meta import META_SCHEMA_VERSION, EnumOption


class SkillMetaOut(BaseModel):
    """技能包来源与启用状态枚举。"""

    source_types: list[EnumOption]
    active_states: list[EnumOption]
    schema_version: str = META_SCHEMA_VERSION
