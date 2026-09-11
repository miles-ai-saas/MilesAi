"""attachments 模块 GET */meta 响应体（与 tenant/attachments/meta.py 字段一致）。"""

from pydantic import BaseModel, Field

from miles_common.schemas.enum_meta import META_SCHEMA_VERSION, EnumOption


class AttachmentMetaOut(BaseModel):
    """附件用途与筛选项枚举。"""

    purposes: list[EnumOption] = Field(description="附件用途枚举")
    purpose_filters: list[EnumOption] = Field(description="用途筛选项枚举")
    schema_version: str = Field(
        default=META_SCHEMA_VERSION,
        description="元数据 schema 版本",
    )
