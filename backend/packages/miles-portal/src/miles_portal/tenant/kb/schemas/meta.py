"""kb 模块 GET */meta 响应体（与 tenant/kb/meta.py 字段一致）。"""

from pydantic import BaseModel, Field

from miles_common.schemas.enum_meta import META_SCHEMA_VERSION, EnumOption


class KbMetaOut(BaseModel):
    """知识库检索模式、来源与文档状态枚举。"""

    retrieval_modes: list[EnumOption] = Field(description="知识库检索模式枚举")
    search_modes: list[EnumOption] = Field(description="单次检索模式枚举（含 default）")
    search_sources: list[EnumOption] = Field(description="检索调用来源枚举")
    document_statuses: list[EnumOption] = Field(description="文档处理状态枚举")
    media_types: list[EnumOption] = Field(description="检索 media_types 过滤枚举")
    schema_version: str = Field(
        default=META_SCHEMA_VERSION,
        description="元数据 schema 版本号",
    )
