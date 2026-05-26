"""attachments 模块 GET */meta 响应体（与 tenant/attachments/meta.py 字段一致）。"""

from pydantic import BaseModel

from app.common.schemas.enum_meta import META_SCHEMA_VERSION, EnumOption


class AttachmentMetaOut(BaseModel):
    """附件用途与筛选项枚举。"""

    purposes: list[EnumOption]
    purpose_filters: list[EnumOption]
    schema_version: str = META_SCHEMA_VERSION
