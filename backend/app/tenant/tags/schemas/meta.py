"""tags 模块 GET /tags/meta 响应体。"""

from pydantic import BaseModel

from app.common.schemas.enum_meta import EnumOption


class TagMetaOut(BaseModel):
    """标签可绑定实体类型枚举。"""

    entity_types: list[EnumOption]
    schema_version: str = "1"
