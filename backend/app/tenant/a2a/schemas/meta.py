"""a2a 模块 GET */meta 响应体（与 tenant/a2a/meta.py 字段一致）。"""

from pydantic import BaseModel

from app.common.schemas.enum_meta import META_SCHEMA_VERSION, EnumOption


class A2aMetaOut(BaseModel):
    """A2A Peer 状态、调用策略与角色枚举。"""

    peer_statuses: list[EnumOption]
    invoke_policies: list[EnumOption]
    peer_role_hints: list[EnumOption]
    schema_version: str = META_SCHEMA_VERSION
