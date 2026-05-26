"""a2a 模块 GET */meta 响应体（与 tenant/a2a/meta.py 字段一致）。"""

from pydantic import BaseModel, Field

from app.common.schemas.enum_meta import META_SCHEMA_VERSION, EnumOption


class A2aMetaOut(BaseModel):
    """A2A Peer 状态、调用策略与角色枚举。"""

    peer_statuses: list[EnumOption] = Field(description="A2A 对端状态枚举")
    invoke_policies: list[EnumOption] = Field(description="调用策略枚举")
    peer_role_hints: list[EnumOption] = Field(description="对端角色提示枚举")
    schema_version: str = Field(
        default=META_SCHEMA_VERSION,
        description="元数据 schema 版本",
    )
