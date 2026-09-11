"""prompts 模块 GET /prompt-templates/meta 响应体。"""

from pydantic import BaseModel, Field

from miles_common.schemas.enum_meta import META_SCHEMA_VERSION, EnumOption


class PromptMetaOut(BaseModel):
    """提示词模板启用状态枚举。"""

    active_states: list[EnumOption] = Field(description="启用状态枚举")
    schema_version: str = Field(
        default=META_SCHEMA_VERSION,
        description="元数据 schema 版本号",
    )
