"""agents 模块 GET */meta 响应体（与 tenant/agents/meta.py 字段一致）。"""

from pydantic import BaseModel

from app.common.schemas.enum_meta import META_SCHEMA_VERSION, EnumOption


class AgentMetaOut(BaseModel):
    """智能体状态、类型、主路径与子智能体角色枚举。"""

    statuses: list[EnumOption]
    agent_types: list[EnumOption]
    sub_agent_role_hints: list[EnumOption]
    primary_paths: list[EnumOption]
    schema_version: str = META_SCHEMA_VERSION
