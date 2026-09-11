"""tags 模块 GET /tags/meta 响应体。"""

from pydantic import BaseModel, Field

from miles_common.schemas.enum_meta import META_SCHEMA_VERSION, EnumOption


class TagMetaOut(BaseModel):
    """标签可绑定实体类型枚举。"""

    entity_types: list[EnumOption] = Field(description="可绑定标签的实体类型枚举")
    schema_version: str = Field(
        default=META_SCHEMA_VERSION,
        description="元数据 schema 版本号",
    )
