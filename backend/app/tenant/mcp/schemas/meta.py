"""mcp 模块 GET */meta 响应体（与 tenant/mcp/meta.py 字段一致）。"""

from pydantic import BaseModel

from app.common.schemas.enum_meta import META_SCHEMA_VERSION, EnumOption


class McpMetaOut(BaseModel):
    """MCP 连接状态、传输类型与同步展示枚举。"""

    statuses: list[EnumOption]
    transport_filters: list[EnumOption]
    transport_types: list[EnumOption]
    sync_displays: list[EnumOption]
    schema_version: str = META_SCHEMA_VERSION
