"""kb 模块 GET */meta 响应体（与 tenant/kb/meta.py 字段一致）。"""

from app.common.schemas.enum_meta import META_SCHEMA_VERSION, EnumOption
from pydantic import BaseModel


class KbMetaOut(BaseModel):
    """知识库检索模式、来源与文档状态枚举。"""

    retrieval_modes: list[EnumOption]
    search_modes: list[EnumOption]
    search_sources: list[EnumOption]
    document_statuses: list[EnumOption]
    schema_version: str = META_SCHEMA_VERSION
