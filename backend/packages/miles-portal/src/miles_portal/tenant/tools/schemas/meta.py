"""tools 模块 GET */meta 响应体（与 tenant/tools/meta.py 字段一致）。"""

from pydantic import BaseModel, Field

from miles_common.schemas.enum_meta import META_SCHEMA_VERSION, EnumOption


class ToolsMetaOut(BaseModel):
    """工具类型、目录来源与调用结果枚举。"""

    tool_types: list[EnumOption] = Field(description="工具类型枚举选项")
    catalog_sources: list[EnumOption] = Field(description="目录来源枚举选项")
    invocation_statuses: list[EnumOption] = Field(description="调用结果状态枚举选项")
    schema_version: str = Field(default=META_SCHEMA_VERSION, description="元数据 schema 版本")
