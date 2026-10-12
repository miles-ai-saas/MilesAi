"""mcp 模块 GET */meta 响应体（与 tenant/mcp/meta.py 字段一致）。"""

from pydantic import BaseModel, Field

from miles_common.schemas.enum_meta import META_SCHEMA_VERSION, EnumOption


class McpStdioTemplateOut(BaseModel):
    """预置 STDIO 启动模板（填入 connection_config.command/args）。"""

    id: str = Field(description="模板 ID")
    label: str = Field(description="展示名称")
    hint: str | None = Field(default=None, description="补充说明")
    command: str = Field(description="启动命令（须在命令白名单内）")
    args: list[str] = Field(default_factory=list, description="参数列表")
    network_mode: str = Field(default="deny", description="deny | allow")


class McpMetaOut(BaseModel):
    """MCP 连接状态、传输类型与同步展示枚举。"""

    statuses: list[EnumOption] = Field(description="MCP 服务状态枚举")
    transport_filters: list[EnumOption] = Field(description="传输类型筛选项枚举")
    transport_types: list[EnumOption] = Field(description="传输类型枚举")
    sync_displays: list[EnumOption] = Field(description="同步状态展示枚举")
    stdio_templates: list[McpStdioTemplateOut] = Field(
        default_factory=list,
        description="预置 STDIO 启动模板",
    )
    schema_version: str = Field(
        default=META_SCHEMA_VERSION,
        description="元数据 schema 版本",
    )
