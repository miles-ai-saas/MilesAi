"""flows 模块 GET */meta 响应体（与 tenant/flows/meta.py 字段一致）。"""

from pydantic import BaseModel, Field

from app.common.schemas.enum_meta import META_SCHEMA_VERSION, EnumOption


class FlowMetaOut(BaseModel):
    """流程发布状态枚举。"""

    statuses: list[EnumOption] = Field(description="流程发布状态枚举")
    schema_version: str = Field(
        default=META_SCHEMA_VERSION,
        description="元数据 schema 版本",
    )
