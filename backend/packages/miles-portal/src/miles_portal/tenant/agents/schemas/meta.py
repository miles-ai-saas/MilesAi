"""agents 模块 GET */meta 响应体（与 tenant/agents/meta.py 字段一致）。"""

from pydantic import BaseModel, Field

from miles_common.schemas.enum_meta import META_SCHEMA_VERSION, EnumOption


class AgentMetaOut(BaseModel):
    """智能体状态、类型、主路径与子智能体角色枚举。"""

    statuses: list[EnumOption] = Field(description="智能体启用状态枚举")
    agent_types: list[EnumOption] = Field(description="智能体类型枚举")
    sub_agent_role_hints: list[EnumOption] = Field(description="子智能体角色提示枚举")
    primary_paths: list[EnumOption] = Field(description="对话主执行路径枚举")
    runtime_modes: list[EnumOption] = Field(description="agent.config.runtime_mode 枚举")
    planners: list[EnumOption] = Field(description="agent.config.planner 枚举")
    schema_version: str = Field(
        default=META_SCHEMA_VERSION,
        description="元数据 schema 版本",
    )
