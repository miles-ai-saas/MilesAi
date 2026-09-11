"""mcp 模块 GET */meta 响应体（与 tenant/mcp/meta.py 字段一致）。"""

from pydantic import BaseModel, Field

from miles_common.schemas.enum_meta import META_SCHEMA_VERSION, EnumOption


class McpMetaOut(BaseModel):
    """MCP 连接状态、传输类型与同步展示枚举。"""

    statuses: list[EnumOption] = Field(description="MCP 服务状态枚举")
    transport_filters: list[EnumOption] = Field(description="传输类型筛选项枚举")
    transport_types: list[EnumOption] = Field(description="传输类型枚举")
    sync_displays: list[EnumOption] = Field(description="同步状态展示枚举")
    schema_version: str = Field(
        default=META_SCHEMA_VERSION,
        description="元数据 schema 版本",
    )
