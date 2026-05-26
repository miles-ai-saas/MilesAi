"""tools 模块 GET */meta 响应体（与 tenant/tools/meta.py 字段一致）。"""

from app.common.schemas.enum_meta import EnumOption
from pydantic import BaseModel


class ToolsMetaOut(BaseModel):
    """工具类型、目录来源与调用结果枚举。"""

    tool_types: list[EnumOption]
    catalog_sources: list[EnumOption]
    invocation_statuses: list[EnumOption]
